"""上市公司年报/10-K 文本特征面板引擎。"""

__version__ = "0.2.2"

from filingtext.features import score_document
from filingtext.sections import split_sections

__all__ = ["__version__", "score_document", "split_sections"]
