from packages.intelligence.normalization.canonical import DurableNormalizer
from packages.intelligence.normalization.cvelist_v5 import CVEListV5HotBugNormalizer
from packages.intelligence.normalization.cvelist_v5_durable import CVEListV5CanonicalNormalizer
from packages.intelligence.normalization.hot_bug import HotBugNormalizer
from packages.intelligence.normalization.nvd import NVDHotBugNormalizer
from packages.intelligence.normalization.nvd_durable import NVDCanonicalNormalizer
from packages.sources.contracts import SourceDefinition


def create_hot_bug_normalizer(source: SourceDefinition) -> HotBugNormalizer:
    if source.adapter_type == "cvelist_v5":
        return CVEListV5HotBugNormalizer()
    if source.adapter_type == "nvd":
        return NVDHotBugNormalizer()
    raise ValueError(f"unsupported hot normalizer adapter_type={source.adapter_type!r}")


def create_durable_bug_normalizer(source: SourceDefinition) -> DurableNormalizer:
    if source.adapter_type == "cvelist_v5":
        return CVEListV5CanonicalNormalizer()
    if source.adapter_type == "nvd":
        return NVDCanonicalNormalizer()
    raise ValueError(f"unsupported durable normalizer adapter_type={source.adapter_type!r}")
