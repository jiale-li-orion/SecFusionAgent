from scripts.run_security_adversarial_benchmark import (
    REQUIRED_CLASSES,
    _probe_mcp_schema_drift,
    _probe_network_policy_bypass,
    _probe_sandbox_escape,
    _probe_side_effect_escalation,
)


def test_td3_v1_adversarial_profile_is_frozen() -> None:
    assert REQUIRED_CLASSES == (
        "indirect_prompt_injection",
        "malicious_document",
        "malicious_tool_output",
        "peer_agent_poisoned_message",
        "memory_experience_poisoning",
        "mcp_schema_drift",
        "capability_escalation",
        "network_policy_bypass",
        "sandbox_filesystem_escape_attempt",
        "credential_exfiltration",
        "side_effect_escalation",
    )


def test_deterministic_adversarial_boundaries_fail_closed() -> None:
    probes = (
        _probe_mcp_schema_drift(),
        _probe_network_policy_bypass(),
        _probe_sandbox_escape(),
        _probe_side_effect_escalation(),
    )
    assert all(item.covered for item in probes)
    assert all(item.passed is True for item in probes)
