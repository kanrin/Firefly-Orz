import json
from loguru import logger
import torch


class Dataset(torch.utils.data.Dataset):
    def __init__(self, file, tokenizer, max_seq_length):
        self.tokenizer = tokenizer
        self.bos_token_id = tokenizer.bos_token_id
        self.eos_token_id = tokenizer.eos_token_id
        self.eos_token = tokenizer.eos_token
        self.bos_token = tokenizer.bos_token
        self.max_seq_length = max_seq_length
        with open(file, 'r', encoding='utf8') as f:
            data_list = f.readlines()
        logger.info("there are {} data in dataset".format(len(data_list)))
        self.data_list = data_list

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, index):
        # 每条数据格式为: <s>input1</s>target1</s>input2</s>target2</s>...
        data = self.data_list[index]
        data = json.loads(data)
        input_text = str(data['input']).strip().replace('<s>', self.bos_token).replace('</s>', self.eos_token)
        target_text = str(data['target']).strip().replace('<s>', self.bos_token).replace('</s>', self.eos_token)

        # target中存在多轮对话
        utterances = [input_text] + target_text.split(self.eos_token)
        utterances = [x.strip() for x in utterances]
        # 奇数个utterance，舍弃最后一个utterance
        if len(utterances) % 2 == 1:
            utterances = utterances[:-1]
        utterances_ids = self.tokenizer(utterances).input_ids

        # 模型的输入格式为：<s>input1</s>target1</s>input2</s>target2</s>...
        input_ids = [self.bos_token_id]
        target_mask = [0]   # 用于对input进行mask，只计算target部分的loss
        for i, utterances_id in enumerate(utterances_ids):
            input_ids += (utterances_id + [self.eos_token_id])
            if i % 2 == 0:
                target_mask += [0]*(len(utterances_id)+1)
            else:
                target_mask += [1] * (len(utterances_id) + 1)
        assert len(input_ids) == len(target_mask)
        # 对长度进行截断
        input_ids = input_ids[:self.max_seq_length]
        target_mask = target_mask[:self.max_seq_length]
        attention_mask = [1] * len(input_ids)
        assert len(input_ids) == len(target_mask) == len(attention_mask)
        inputs = {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'target_mask': target_mask
        }
        return inputs
