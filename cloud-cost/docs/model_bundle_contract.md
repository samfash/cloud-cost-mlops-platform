# artifacts/model_bundle

## Config

config/config.yaml needs a model_packager section. ModelPackagerConfig fields: root_dir, model_path, label_encoders_path, feature_schema_path, metrics_path, r2_minor_bump_threshold, r2_major_bump_threshold, mae_regression_tolerance, r2_floor, mae_ceiling, allow_nonimproving_patch.

ConfigurationManager.get_model_packager_config() returns it. Gate defaults in that field order: 0.05, 0.15, 0.05, 0.0, 1.0e9, true.

## Paths

HEAD — regular file whose text is the active version plus one newline (not a symlink).
pins.json — {"anchor": "<version>", "probe": "<version>" or null}, written with indent=2, sort_keys=True, and a trailing newline.
RELEASES — append-only UTF-8 ledger. Each successful publish appends exactly one line using pathlib.Path.open in append mode (for example `(root / "RELEASES").open("a", encoding="utf-8")`), not the builtin `open()` function.
catalog.sqlite — sqlite3 with journal_mode=WAL; delete and recreate on every successful publish; PRAGMA foreign_keys=ON; populate inside BEGIN IMMEDIATE; after commit run PRAGMA wal_checkpoint(TRUNCATE).
.publish.lock — must exist after packaging; model_packager.py uses import fcntl at module level and fcntl.flock(..., fcntl.LOCK_EX) (blocking, not LOCK_EX|LOCK_NB) for the critical section.
.publish.journal — created with os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY) after version assignment, contents "<version>\n"; removed only after HEAD is published; must not remain after refused cleanup.
objects/<aa>/<bb>/<rest> — lowercase SHA-256 content-addressed blobs; digests of configured source files use hashlib.file_digest.
versions/<MAJOR.MINOR.PATCH>/manifest.json — only file allowed in that directory.

Semver directories must not sit directly under model_bundle/. Successful promotion removes any leftover latest pointer. After success or refused cleanup, no .staging-* paths remain. Older versions and earlier RELEASES lines are immutable.

Candidates assemble under .staging-<version> via pathlib.Path.mkdir (not os.makedirs), then move with os.replace into versions/<version>/.

## Publish sequence

Under the held LOCK_EX, after gate acceptance assigns a version, the successful path must perform these steps in order:

1. Create .publish.journal with O_CREAT|O_EXCL|O_WRONLY and write "<version>\n"
2. CAS-store model.pkl from the configured path
3. CAS-store label_encoders.pkl from the configured path
4. CAS-store metrics.json from the configured path
5. Build feature_columns.json (with the new model_version) and CAS-store it
6. Create .staging-<version> with pathlib.Path.mkdir
7. Write staging/manifest.json
8. os.replace staging directory into versions/<version>/
9. Append one line to RELEASES via pathlib.Path.open(..., "a", ...) (not builtin open)
10. Delete catalog.sqlite if it exists
11. Recreate catalog.sqlite (WAL, foreign_keys=ON, BEGIN IMMEDIATE, insert packages/blobs)
12. PRAGMA wal_checkpoint(TRUNCATE)
13. Atomically publish pins.json (temp + os.replace)
14. Atomically publish HEAD (temp + os.replace)
15. Remove .publish.journal
16. Remove leftover latest if present
17. Remove any remaining .staging-* paths

## Blobs

Required logical names: model.pkl, label_encoders.pkl, metrics.json, feature_columns.json.

Optional latency adjuncts (same version; not cost-gated): latency_model.pkl, latency_feature_columns.json, latency_metrics.json.

model.pkl, label_encoders.pkl, and metrics.json must match the configured training/evaluation files byte-for-byte. feature_columns.json carries training feature_order, n_features equal to len(feature_order), and model_version set to the newly assigned version before the bytes are hashed into the object store.

## Manifest

Required fields: model_version, parent_version, created_at, promotion_class, bundle_epoch, blobs, digest_ring, lineage_token, seal_tag, publish_nonce, binding_mac.

parent_version is null on 1.0.0 / bootstrap, otherwise the previous highest published semver.
created_at is UTC ending in Z (example 2024-06-01T12:00:00.000000Z; +00:00 is invalid) and must be strictly greater than the parent's created_at when a parent exists.
blobs maps each logical name to {"sha256":"...","size":...}.
publish_nonce is secrets.token_hex(8) (sixteen lowercase hex characters) for each successful publish.
digest_ring is the lowercase hex of hashlib.blake2b(data, digest_size=32, person=b"mpip-ring").digest() where data is struct.pack(">I", bundle_epoch) followed by the four raw 32-byte digests of model.pkl, metrics.json, label_encoders.pkl, and feature_columns.json in that descending filename order. Optional latency blobs are listed in manifest.blobs but are excluded from digest_ring so the cost seal stays stable.
lineage_token is the lowercase hex SHA-256 of the UTF-8 string {parent_version or "ROOT"}|{model_version}|{digest_ring}.
seal_tag is the lowercase hex of hashlib.blake2b(lineage_token.encode(), digest_size=16, person=b"mpip-seal").digest().
binding_mac is the lowercase hex of hmac.new(key, msg, hashlib.sha256).digest() where key = hashlib.blake2b(publish_nonce.encode(), digest_size=16, person=b"mpip-mac").digest() and msg = f"{seal_tag}|{digest_ring}".encode().
bundle_epoch is 7 on bootstrap, parent bundle_epoch plus one on major_gain, otherwise equal to the parent epoch.
The first promotion is 1.0.0 with promotion_class bootstrap.

## Gates

Compare only the candidate holdout metrics JSON and feature schema JSON to the highest published parent. model_packager.py must not contain .predict(.

delta_R2 = new_R2 - parent_R2
mae_rel = (new_MAE - parent_MAE) / max(parent_MAE, 1e-12)
A schema break is any change in feature_order or n_features versus the parent's packaged feature_columns.

| Pri | Condition | Outcome |
|---|---|---|
| 1 | missing MAE, MSE, RMSE, or R2 | refuse |
| 2 | R2 below r2_floor or MAE above mae_ceiling | refuse |
| 3 | no parent | 1.0.0 / bootstrap |
| 4 | schema break and delta_R2 >= minor and mae_rel <= tolerance | minor (patch 0) / schema_break_accepted; else refuse |
| 5 | delta_R2 >= major and mae_rel <= 0 | (MAJOR+1).0.0 / major_gain |
| 6 | delta_R2 >= minor and mae_rel <= 0 | minor bump / minor_gain |
| 7 | delta_R2 >= minor and 0 < mae_rel <= tolerance | patch / minor_gain_mae_soft |
| 8 | delta_R2 >= minor and mae_rel > tolerance | refuse |
| 9 | delta_R2 >= 0 and mae_rel <= 0 | patch / stable_or_better |
| 10 | delta_R2 >= 0 and mae_rel > 0 | patch / r2_ok_mae_worse if allow_nonimproving_patch else refuse |
| 11 | delta_R2 < 0 and mae_rel < 0 | patch / tradeoff_mae if allow_nonimproving_patch else refuse |
| 12 | otherwise | refuse |

Only major_gain increments MAJOR. Re-promoting unchanged metrics advances PATCH unless a bump outcome applies.

bootstrap, major_gain, minor_gain, schema_break_accepted, and stable_or_better set anchor to the new version and probe to null. minor_gain_mae_soft, r2_ok_mae_worse, and tradeoff_mae set probe to the new version and leave anchor unchanged. Active inference uses probe when set, otherwise anchor. After success, HEAD equals that active version plus a newline. pins.json and HEAD are published via a temp file and os.replace.

## RELEASES

One line per success: <unix_ms> <version> <promotion_class> <digest_ring> <lineage_token> <publish_nonce> <binding_mac>\n

Append that line with pathlib.Path.open in mode "a" (UTF-8). Builtin open(...) is not accepted for this ledger write.

## catalog.sqlite packages

Ascending semver rows: version TEXT PRIMARY KEY, parent_version TEXT, created_at TEXT NOT NULL, promotion_class TEXT NOT NULL, bundle_epoch INTEGER NOT NULL, r2 REAL NOT NULL, mae REAL NOT NULL, digest_ring TEXT NOT NULL, lineage_token TEXT NOT NULL, seal_tag TEXT NOT NULL, publish_nonce TEXT NOT NULL, binding_mac TEXT NOT NULL.

## catalog.sqlite blobs

sha256 TEXT PRIMARY KEY, logical_name TEXT NOT NULL, size INTEGER NOT NULL, first_seen_version TEXT NOT NULL (oldest version that referenced the digest).

## Inference

Load HEAD, then versions/<version>/manifest.json, resolve each blob under the three-level objects path, verify digest and size, recompute and verify binding_mac with hmac.compare_digest, and raise CustomException on mismatch. bundle_dir is that versions/<version> directory (not the model_bundle root). Expose model_version, metrics, and feature_columns. predict() receives a DataFrame already in packaged feature_order form and only reindexes; it must not re-run categorical encoding. Inference must work when training-stage directories are gone.
