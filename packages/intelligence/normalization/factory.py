from packages.intelligence.normalization.hot_bug import HotBugNormalizer
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.sources.contracts import SourceDefinition


def create_hot_bug_normalizer(source: SourceDefinition) -> HotBugNormalizer:
    if source.adapter_type == "nvd":
        return NVDHotBugNormalizer()
    raise ValueError(f"unsupported hot normalizer adapter_type={source.adapter_type!r}")
