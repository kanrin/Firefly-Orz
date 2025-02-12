from transformers import (
    set_seed,
    HfArgumentParser,
    TrainingArguments,
    Trainer
)
import argparse
from loguru import logger
import os
from os.path import join
import torch
from transformers import AutoTokenizer
from component.model import BloomForCausalLM
from component.collator import DataCollator
from component.dataset import Dataset
from component.argument import CustomizedArguments
from component.trainer import Trainer


def setup_everything():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_args_file", type=str, default='train_args/finetune.json', help="")
    args = parser.parse_args()
    train_args_file = args.train_args_file
    # train_args_file = 'train_args/finetune.json'
    # 读取训练的参数配置
    parser = HfArgumentParser((CustomizedArguments, TrainingArguments))
    # 解析得到自定义参数，以及自带参数
    args, training_args = parser.parse_json_file(json_file=train_args_file)
    # 创建输出目录
    if not os.path.exists(training_args.output_dir):
        os.makedirs(training_args.output_dir)
    logger.add(join(training_args.output_dir, 'train.log'))
    logger.info("train_args:{}".format(training_args))
    # 设置随机种子
    set_seed(training_args.seed)
    return args, training_args


def init_components(args, training_args):
    """
    初始化各个组件
    """
    world_size = int(os.environ.get("WORLD_SIZE", 1))
    ddp = world_size != 1
    if ddp:
        device_map = {"": int(os.environ.get("LOCAL_RANK") or 0)}
    training_args.ddp_find_unused_parameters = False if ddp else None

    # 加载tokenzier
    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path)
    # 初始化model
    model = BloomForCausalLM.from_pretrained(
        args.model_name_or_path,
        torch_dtype=torch.float16
    )
    # 加载训练集
    train_dataset = Dataset(args.train_file, tokenizer, args.max_seq_length)
    data_collator = DataCollator(tokenizer, args.max_seq_length)

    # 初始化Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator
    )
    return trainer


def main():
    # 进行一些配置和检查
    args, training_args = setup_everything()
    # 加载各种组件
    trainer = init_components(args, training_args)
    # 开始训练
    logger.info("*** starting training ***")
    train_result = trainer.train()
    # 保存最好的checkpoint
    final_save_path = join(training_args.output_dir, 'final')
    trainer.save_model(final_save_path)  # Saves the tokenizer too
    # 保存训练指标
    metrics = train_result.metrics
    trainer.log_metrics("train", metrics)
    trainer.save_metrics("train", metrics)
    trainer.save_state()


if __name__ == "__main__":
    main()
