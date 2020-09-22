"""
core 模块里实现了 backend 的核心框架，常用的功能都可以从 backend 包中直接 import。当然你也同样可以从 core 模块的子模块中 import，
例如 :class:`~backend.DataSetIter` 组件有两种 import 的方式::
    
    # 直接从 backend 中 import
    from backend import DataSetIter
    
    # 从 core 模块的子模块 batch 中 import DataSetIter
    from backend.core.batch import DataSetIter

对于常用的功能，你只需要在 :mod:`backend` 中查看即可。如果想了解各个子模块的具体作用，您可以在下面找到每个子模块的具体文档。

"""
__all__ = [
    "DataSet",
    
    "Instance",
    
    "FieldArray",
    "Padder",
    "AutoPadder",
    "EngChar2DPadder",
    
    "Vocabulary",
    
    "DataSetIter",
    "BatchIter",
    "TorchLoaderIter",
    
    "Const",
    
    "Tester",
    "Trainer",
    
    "cache_results",
    "seq_len_to_mask",
    "get_seq_len",
    "logger",
    
    "Callback",
    "GradientClipCallback",
    "EarlyStopCallback",
    "FitlogCallback",
    "EvaluateCallback",
    "LRScheduler",
    "ControlC",
    "LRFinder",
    "TensorboardCallback",
    "WarmupCallback",
    'SaveModelCallback',
    "CallbackException",
    "EarlyStopError",
    
    "LossFunc",
    "CrossEntropyLoss",
    "L1Loss",
    "BCELoss",
    "NLLLoss",
    "LossInForward",
    "CMRC2018Loss",
    
    "AccuracyMetric",
    "SpanFPreRecMetric",
    "CMRC2018Metric",

    "Optimizer",
    "SGD",
    "Adam",
    "AdamW",
    
    "SequentialSampler",
    "BucketSampler",
    "RandomSampler",
    "Sampler",
]

from ._logger import logger
from .batch import DataSetIter, BatchIter, TorchLoaderIter
from .callback import Callback, GradientClipCallback, EarlyStopCallback, FitlogCallback, EvaluateCallback, \
    LRScheduler, ControlC, LRFinder, TensorboardCallback, WarmupCallback, SaveModelCallback, CallbackException, \
    EarlyStopError
from .const import Const
from .dataset import DataSet
from .field import FieldArray, Padder, AutoPadder, EngChar2DPadder
from .instance import Instance
from .losses import LossFunc, CrossEntropyLoss, L1Loss, BCELoss, NLLLoss, LossInForward, CMRC2018Loss
from .metrics import AccuracyMetric, SpanFPreRecMetric, CMRC2018Metric
from .optimizer import Optimizer, SGD, Adam, AdamW
from .sampler import SequentialSampler, BucketSampler, RandomSampler, Sampler
from .tester import Tester
from .trainer import Trainer
from .utils import cache_results, seq_len_to_mask, get_seq_len
from .vocabulary import Vocabulary
