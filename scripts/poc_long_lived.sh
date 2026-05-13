#!/usr/bin/env bash
# Long-lived token keychain wrap POC
# Usage: bash scripts/poc_long_lived.sh
#
# A1: keychain wrap된 long-lived token을 Claude Code가 정상 사용하는가
# A2: long-lived token이 /api/oauth/usage에 어떻게 응답하는가 (403 expected)
# A3: 토큰 prefix가 sk-ant- 인가
# A4: keychain wrap 토큰이 refresh 시도 없이 사용되는가
set -e

echo "=== Long-lived Token POC ==="
echo
echo "1. claude setup-token 으로 토큰을 발급하고 prompt에 paste하세요."
echo "   터미널 다른 창에서: claude setup-token"
read -rsp "토큰: " TOKEN
echo

if [[ "$TOKEN" != sk-ant-* ]]; then
  echo "[FAIL] A3: 토큰 포맷이 예상과 다릅니다 (sk-ant- prefix 아님)"
  echo "       실제 prefix: ${TOKEN:0:12}..."
  exit 1
fi

echo "[PASS] A3: 토큰 prefix OK ($(echo "$TOKEN" | cut -d- -f1-3))"
echo

echo "[A2] /api/oauth/usage 호출"
HTTP_CODE=$(curl -s -o /tmp/poc_usage.json -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20" \
  https://api.anthropic.com/api/oauth/usage)
echo "    HTTP $HTTP_CODE"
echo "    Body:"
cat /tmp/poc_usage.json
echo
echo

EXPIRES_MS=$(python3 -c "from datetime import datetime, timedelta; print(int((datetime.now()+timedelta(days=365)).timestamp()*1000))")
WRAPPED=$(python3 -c "
import json, sys
print(json.dumps({'claudeAiOauth': {
    'accessToken': sys.argv[1],
    'refreshToken': '',
    'expiresAt': int(sys.argv[2]),
    'subscriptionType': 'max',
    'rateLimitTier': 'default_claude_max_20x',
}}, ensure_ascii=False))
" "$TOKEN" "$EXPIRES_MS")

echo "[A1/A4] keychain wrap → claude 기동 테스트"
echo
echo "    아래 명령을 별도 터미널에서 직접 실행하여 검증:"
echo
echo "    # 기존 credential 백업"
echo "    security find-generic-password -s 'Claude Code-credentials' -a \$USER -w > /tmp/backup.json 2>/dev/null"
echo
echo "    # wrap된 토큰 주입"
echo "    security delete-generic-password -s 'Claude Code-credentials' -a \$USER 2>/dev/null"
echo "    security add-generic-password -s 'Claude Code-credentials' -a \$USER -w \"$WRAPPED\""
echo
echo "    # claude 기동 테스트 (별도 터미널에서)"
echo "    claude --print 'say hello briefly'"
echo
echo "    # 복원 (테스트 후)"
echo "    security delete-generic-password -s 'Claude Code-credentials' -a \$USER 2>/dev/null"
echo "    security add-generic-password -s 'Claude Code-credentials' -a \$USER -w \"\$(cat /tmp/backup.json)\""
echo
echo "검증 결과 (PASS/FAIL/HTTP code)를 docs/superpowers/specs/2026-05-13-long-lived-token-design.md Section 11에 기록하세요."
