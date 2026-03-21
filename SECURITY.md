# Security Policy

## 対応方針

- 依存関係の脆弱性は `cargo audit`、`cargo deny`、`pip-audit` で継続確認します
- 問題報告を受けた場合は再現性、影響範囲、回避策を優先して整理します

## 報告方法

公開Issueへ機微情報を書かず、保守者へ非公開で連絡してください。

## 依存関係更新

- lock file はコミット対象です
- Python / Rust 両方の依存更新時は CI と examples の両方を確認してください
