# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-02-01

### Changed
- README 간소화 및 Mermaid 다이어그램 추가
- 상세 문서는 docs/ARCHITECTURE.md로 분리

## [1.1.0] - 2026-02-01

### Fixed
- OAuth 토큰 갱신 엔드포인트 수정 (`platform.claude.com/v1/oauth/token`)
- 올바른 client_id 사용

### Added
- 세션 시작 시 모든 계정 토큰 자동 갱신
- release skill 추가

## [1.0.0] - 2026-01-31

### Added
- 초기 릴리스
- 다중 계정 관리 (add, switch, remove)
- 사용량 모니터링 (시각화 바)
- OAuth 토큰 자동 갱신
- SessionStart Hook으로 자동 계정 등록
- Max5/Max20 플랜 지원
