# Test matrix

This document specifies the minimum test coverage expected for v1.

The goal is not huge test volume.
The goal is to make the lab trustworthy where it matters.

## Coverage principles

1. stable lab infrastructure gets stronger tests than the mutable research layer
2. every user-facing CLI contract should have at least one integration path
3. every novel algorithm should have at least one deterministic unit test
4. GPU tests must be tiny and targeted
5. fake targets should cover the runner before real GPU coverage exists

## Phase 0 tests

### Unit
- `test_settings_precedence`
- `test_settings_default_paths`
- `test_paths_repo_discovery`
- `test_paths_refuse_escape_outside_repo`

### Integration
- `test_cli_help`
- `test_bootstrap_creates_managed_roots`
- `test_preflight_json_contract`

## Phase 1 tests

### Unit
- `test_crash_classifier_import_error`
- `test_crash_classifier_oom_train`
- `test_crash_classifier_oom_eval`
- `test_crash_classifier_timeout`
- `test_crash_classifier_unknown`

### Integration
- `test_runner_success_fake_target`
- `test_runner_failure_fake_target`
- `test_manifest_written_before_launch`
- `test_artifact_index_written`
- `test_schema_validation_failure_marks_run_failed`

## Phase 2 tests

### Unit
- `test_campaign_manifest_validation`
- `test_config_fingerprint_stable`
- `test_offline_packer_deterministic`
- `test_offline_packer_preserves_bos_alignment`
- `test_split_rules_base_2k`

### Integration
- `test_campaign_build_idempotent`
- `test_campaign_verify_detects_hash_mismatch`
- `test_campaign_build_writes_manifests`

## Phase 3 tests

### Unit
- `test_promotion_rule_below_threshold`
- `test_promotion_rule_simple_win`
- `test_promotion_rule_tie_prefers_lower_complexity`
- `test_report_metric_delta_rounding`

### Integration
- `test_score_explains_promotion_decision`
- `test_replay_creates_new_experiment_linked_to_source`
- `test_pre_eval_checkpoint_retained_until_scored`

## Phase 4 tests

### Unit
- `test_scheduler_respects_lane_mix`
- `test_scheduler_prefers_ablation_after_complex_win`
- `test_scheduler_avoids_duplicate_config_fingerprint`
- `test_archive_keeps_pareto_and_near_miss`
- `test_novelty_tagging`

### Integration
- `test_queue_fill_from_archive_state`
- `test_export_code_proposal_pack_contract`

## Phase 5 tests

### Unit
- `test_search_space_legality`
- `test_mutation_rules_respect_campaign_constraints`
- `test_backend_selector_cache_hit`
- `test_backend_selector_blacklist_fallback`

### GPU
- `test_tiny_gpu_run_emits_summary`
- `test_backend_selector_runs_microbench`
- `test_config_summary_has_backend_and_device_profile`

## Phase 6 tests

### Integration
- `test_report_generation`
- `test_leaderboard_campaign_local_only`
- `test_champion_card_generation`
- `test_night_session_fake`
- `test_report_contains_recommendations`

## Phase 7 tests

### Unit
- `test_cleanup_never_deletes_retained_classes`
- `test_resume_reconstructs_interrupted_queue`
- `test_doctor_detects_missing_artifacts`

### GPU
- `test_smoke_cli_gpu`

## Contract fixtures

The pack includes fixtures intended to reduce boilerplate:

- `tests/fixtures/fake_target_success.py`
- `tests/fixtures/fake_target_failure.py`
- `tests/fixtures/contracts/sample_campaign.json`
- `tests/fixtures/contracts/sample_proposal.json`
- `tests/fixtures/contracts/sample_run_manifest.json`
- `tests/fixtures/contracts/sample_summary.json`

## Minimum acceptance for merge

A phase should not be considered done unless the tests listed for that phase exist and pass for the relevant environment.
