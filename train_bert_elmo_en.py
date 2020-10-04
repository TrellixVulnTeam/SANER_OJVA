from models.SANER import SAModel
from fastNLP.embeddings import CNNCharEmbedding
from fastNLP import cache_results
from fastNLP import Trainer, GradientClipCallback, WarmupCallback
from torch import optim
from fastNLP import SpanFPreRecMetric, BucketSampler
from fastNLP.io.pipe.conll import OntoNotesNERPipe
from fastNLP.embeddings import StaticEmbedding, StackEmbedding, LSTMCharEmbedding, ElmoEmbedding, BertEmbedding
from modules.TransformerEmbedding import TransformerCharEmbed
from modules.pipe import Conll2003NERPipe, WNUT_17NERPipe
from modules.callbacks import EvaluateCallback

from get_context import get_neighbor_for_vocab, build_instances

import os
import argparse
from datetime import datetime

import random
import numpy as np
import torch


parser = argparse.ArgumentParser()

parser.add_argument('--dataset', type=str,
                    default='en-ontonotes', choices=['conll2003', 'en-ontonotes', 'WNUT_16_train', 'WNUT_17_train'])
parser.add_argument('--seed', type=int, default=20)
parser.add_argument('--log', type=str, default=None)
parser.add_argument('--lr', type=float, default=0.0001)
parser.add_argument('--context_num', type=int, default=10)
parser.add_argument('--glove_path', type=str)
parser.add_argument('--bert_model', type=str, required=True)
parser.add_argument('--pool_method', type=str, default="first", choices=["first", "last", "avg", "max"])
parser.add_argument('--trans_dropout', type=float, default=0.2)
parser.add_argument('--fc_dropout', type=float, default=0.4)
parser.add_argument('--memory_dropout', type=float, default=0.2)
parser.add_argument('--fusion_type', type=str, default='gate-concat',
                    choices=['concat', 'add', 'concat-add', 'gate-add', 'gate-concat'])
parser.add_argument('--fusion_dropout', type=float, default=0.2)
parser.add_argument('--highway_layer', type=int, default=0)
parser.add_argument('--kv_attn_type', type=str, default='dot')

args = parser.parse_args()


def setup_seed(seed):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

setup_seed(args.seed)

dataset = args.dataset
if dataset == 'en-ontonotes':
    n_heads = 10
    head_dims = 96
    num_layers = 2
    lr = args.lr    # default: 0.0009
    attn_type = 'adatrans'
    optim_type = 'sgd'
    trans_dropout = args.trans_dropout  # default: 0.15
    batch_size = args.batch_size
elif dataset in ['conll2003', 'conll2003_train']:
    n_heads = 12
    head_dims = 128
    num_layers = 2
    lr = args.lr    # default: 0.0001
    attn_type = 'adatrans'
    optim_type = 'adam'
    trans_dropout = args.trans_dropout  # 有可能是0.4
    batch_size = args.batch_size
elif dataset in ['WNUT_17', 'WNUT_17_train', 'WNUT_16', 'WNUT_16_train']:
    n_heads = 12
    head_dims = 128
    num_layers = 2
    lr = args.lr    # defalut: 0.0001
    attn_type = 'adatrans'
    optim_type = 'adam'
    trans_dropout = args.trans_dropout  # 有可能是0.4
    batch_size = 32
# else:
#     raise RuntimeError("Only support conll2003, en-ontonotes")


char_type = 'adatrans'
embed_size = 30

# positional_embedding
pos_embed = None

model_type = 'elmo'
elmo_model = "en-original"
warmup_steps = 0.01
after_norm = 1
fc_dropout = args.fc_dropout
normalize_embed = True

encoding_type = 'bioes'
d_model = n_heads * head_dims
dim_feedforward = int(2 * d_model)
context_num = args.context_num
glove_path = args.glove_path

device = "cuda"
# device = "cpu"

# new_add
feature_level = "all"
memory_dropout = args.memory_dropout
fusion_dropout = args.fusion_dropout
kv_attn_type = args.kv_attn_type
fusion_type = args.fusion_type
highway_layer = args.highway_layer


def print_time():
    now = datetime.now()
    return "-".join([str(now.year), str(now.month), str(now.day), str(now.hour), str(now.minute), str(now.second)])


name = 'caches/elmo_{}_{}_{}_{}_{}_{}.pkl'.format(dataset, model_type, encoding_type, char_type,
                                                     normalize_embed, context_num)
save_path = "ckpt/elmo_{}_{}_{}_{}.pth".format(dataset, model_type, context_num, print_time())
# save_path = None

logPath = args.log
if not args.log:
    logPath = "log/log_{}_{}_{}.txt".format(dataset, context_num, print_time())


def write_log(sent):
    with open(logPath, "a+", encoding="utf-8") as f:
        f.write(sent)
        f.write("\n")


write_log("=" * 10 + "Start Hyber Parameters" + "=" * 10)

write_log("seed: " + str(args.seed) + "\n")

write_log("dataset: " + dataset)
write_log("batch_size: " + str(batch_size))
write_log("char_embeddings: ")
write_log("char_type: " + char_type)
write_log("embed_size: " + str(embed_size) + "\n")

write_log("elmo_embedding: ")
write_log("model: " + elmo_model)
write_log("normalized_embed: " + str(normalize_embed) + "\n")

write_log("TENER: ")
write_log("n_heads: " + str(n_heads))
write_log("head_dims: " + str(head_dims))
write_log("num_layers: " + str(num_layers))
write_log("lr: " + str(lr))
write_log("attn_type: " + str(attn_type))
write_log("optim_type: " + str(optim_type))
write_log("trans_dropout: " + str(trans_dropout))
write_log("pos_embed: " + str(pos_embed) + "\n")

write_log("KV: ")
write_log("value_vocab: " + str(feature_level))
write_log("scale: " + str(True))
write_log("kv_attn_type: " + kv_attn_type)
write_log("fusion_type: " + fusion_type)
write_log("fusion_dropout: " + str(fusion_dropout))
write_log("memory_dropout: " + str(memory_dropout) + "\n")

write_log("FC: ")
write_log("fc_dropout: " + str(fc_dropout) + "\n")

write_log("optimizer: ")
write_log("optim_type: " + optim_type)
write_log("warmup_steps: " + str(warmup_steps))
write_log("lr: " + str(lr))
write_log("=" * 10 + "End Hyber Parameters" + "=" * 10)


#  scale为1时，同时character和模型的scale都是1


@cache_results(name, _refresh=False)
def load_data():
    # 替换路径
    # 载入数据
    if dataset == 'conll2003':
        # conll2003的lr不能超过0.002
        paths = {'test': "../data/conll2003/test.txt",
                 'train': "../data/conll2003/train.txt"}
        data = Conll2003NERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == 'conll2003_train':
        # conll2003Z~DlrMC?EG0.002
        paths = {'test': "../data/conll2003_train/test.txt",
                 'train': "../data/conll2003_train/train.txt"}
        data = Conll2003NERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == 'en-ontonotes':
        paths = '../data/en-ontonotes/english'
        data = OntoNotesNERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == "WNUT_17":
        paths = {"train": "../data/WNUT_17/train.txt", "test": "../data/WNUT_17/test.txt"}
        data = WNUT_17NERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == "WNUT_17_train":
        paths = {"train": "../data/WNUT_17_train/train.txt", "test": "../data/WNUT_17_train/test.txt"}
        data = WNUT_17NERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == "WNUT_16":
        paths = {"train": "../data/WNUT_16/train.txt", "test": "../data/WNUT_16/test.txt"}
        data = WNUT_17NERPipe(encoding_type=encoding_type).process_from_file(paths)
    elif dataset == "WNUT_16_train":
        paths = {"train": "../data/WNUT_16_train/train.txt", "test": "../data/WNUT_16_train/test.txt"}
        data = WNUT_17NERPipe(encoding_type=encoding_type).process_from_file(paths)

    dict_save_path = os.path.join("../data/{}/data.pth".format(dataset))
    context_dict, context_word2id, context_id2word = get_neighbor_for_vocab(
        data.get_vocab('words').word2idx, glove_path, dict_save_path
    )

    train_feature_data, test_feature_data = build_instances(
        "../data/{}".format(dataset), context_num, context_dict
    )

    # 载入embedding
    # 1. character embedding, training，使用TransformerEncoder
    char_embed = None
    # if char_type == 'cnn':
    #     char_embed = CNNCharEmbedding(vocab=data.get_vocab('words'), embed_size=embed_size, char_emb_size=embed_size, filter_nums=[30],
    #                                   kernel_sizes=[3], word_dropout=0, dropout=0.3, pool_method='max'
    #                                   , include_word_start_end=False, min_char_freq=2)
    # elif char_type in ['adatrans', 'naive']:
    #     char_embed = TransformerCharEmbed(vocab=data.get_vocab('words'), embed_size=embed_size, char_emb_size=embed_size, word_dropout=0,
    #                                       dropout=0.3, pool_method='max', activation='relu',
    #                                       min_char_freq=2, requires_grad=True, include_word_start_end=False,
    #                                       char_attn_type=char_type, char_n_head=3, char_dim_ffn=60, char_scale=char_type=='naive',
    #                                       char_dropout=0.15, char_after_norm=True)
    # elif char_type == 'lstm':
    #     char_embed = LSTMCharEmbedding(vocab=data.get_vocab('words'), embed_size=embed_size, char_emb_size=embed_size, word_dropout=0,
    #                                    dropout=0.3, hidden_size=100, pool_method='max', activation='relu',
    #                                    min_char_freq=2, bidirectional=True, requires_grad=True, include_word_start_end=False)
    # 2. Word Embedding，100维，使用Glove
    # word_embed = StaticEmbedding(vocab=data.get_vocab('words'),
    #                              model_dir_or_name='en-glove-6b-100d',
    #                              requires_grad=True, lower=True, word_dropout=0, dropout=0.5,
    #                              only_norm_found_vector=normalize_embed)
    data.rename_field('words', 'chars')
    # 3. Contextual Embedding, 使用ELMo预训练模型, char-level
    embed = ElmoEmbedding(vocab=data.get_vocab('chars'), model_dir_or_name=elmo_model, layers='mix', requires_grad=False,
                          word_dropout=0.0, dropout=0.5, cache_word_reprs=False)
    embed.set_mix_weights_requires_grad()

    bert_embed = BertEmbedding(vocab=data.get_vocab('chars'), model_dir_or_name=args.bert_model, layers='-1',
                               pool_method=args.pool_method, word_dropout=0, dropout=0.5, include_cls_sep=False,
                               pooled_cls=True, requires_grad=False, auto_truncate=False)

    # Stack Embedding, 把这三种embedding结合起来
    embed = StackEmbedding([embed, bert_embed], dropout=0, word_dropout=0.02)

    return data, embed, train_feature_data, test_feature_data, context_word2id, context_id2word


data_bundle, embed, train_feature_data, test_feature_data, feature2id, id2feature = load_data()

train_data = list(data_bundle.get_dataset("train"))
test_data = list(data_bundle.get_dataset("test"))

print(len(train_data), len(train_feature_data))
print(len(test_data), len(test_feature_data))

vocab_size = len(data_bundle.get_vocab('chars'))
feature_vocab_size = len(feature2id)

model = SAModel(tag_vocab=data_bundle.get_vocab('target'), embed=embed, num_layers=num_layers,
              d_model=d_model, n_head=n_heads,
              feedforward_dim=dim_feedforward, dropout=trans_dropout,
              after_norm=after_norm, attn_type=attn_type,
              bi_embed=None,
              fc_dropout=fc_dropout,
              pos_embed=pos_embed,
              scale=attn_type=='naive',
              vocab_size=vocab_size,
              feature_vocab_size=feature_vocab_size,
              kv_attn_type=kv_attn_type,
              memory_dropout=memory_dropout,
              fusion_dropout=fusion_dropout,
              fusion_type=fusion_type,
              highway_layer=highway_layer
              )

print("Parameter Num: ", sum(param.numel() for param in model.parameters() if param.requires_grad))
print("Parameter Num: ", sum(param.numel() for param in model.kv_memory.parameters() if param.requires_grad))

# params = [name for name, param in model.named_parameters()]
# for param in params:
#     print(param)
# exit()

if optim_type == 'sgd':
    optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9)
else:
    optimizer = optim.Adam(model.parameters(), lr=lr, betas=(0.9, 0.99))

callbacks = []
clip_callback = GradientClipCallback(clip_type='value', clip_value=5)
evaluate_callback = EvaluateCallback(data=data_bundle.get_dataset('test'),
                                     test_feature_data=test_feature_data,
                                     feature2id=feature2id,
                                     id2feature=id2feature,
                                     context_num=context_num
                                     )

if warmup_steps > 0:
    warmup_callback = WarmupCallback(warmup_steps, schedule='linear')
    callbacks.append(warmup_callback)
callbacks.extend([clip_callback, evaluate_callback])

trainer = Trainer(data_bundle.get_dataset('train'), model, optimizer, batch_size=batch_size, sampler=BucketSampler(),
                  num_workers=0, n_epochs=50, dev_data=data_bundle.get_dataset('test'),
                  metrics=SpanFPreRecMetric(tag_vocab=data_bundle.get_vocab('target'), encoding_type=encoding_type),
                  dev_batch_size=batch_size, callbacks=callbacks, device=device, test_use_tqdm=False,
                  use_tqdm=True, print_every=300, save_path=save_path,
                  use_knowledge=True,
                  train_feature_data=train_feature_data,
                  test_feature_data=test_feature_data,
                  feature2id=feature2id,
                  id2feature=id2feature,
                  logger_func=write_log,
                  context_num=context_num
                  )

trainer.train(load_best_model=False)
