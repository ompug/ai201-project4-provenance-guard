#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"

echo "== Submit text =="
curl -s -X POST "$BASE_URL/submit" \
  -H "Content-Type: application/json" \
  -d '{"text":"The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.","creator_id":"demo-user-1"}'
echo
echo

echo "== Submit metadata =="
curl -s -X POST "$BASE_URL/submit/metadata" \
  -H "Content-Type: application/json" \
  -d '{"creator_id":"demo-user-2","content_type":"image_description","image_description":"A handwritten grocery list on a fridge magnet with crossed-out items and a coffee stain in the corner."}'
echo
echo

echo "== Verify creator =="
curl -s -X POST "$BASE_URL/certificate/verify" \
  -H "Content-Type: application/json" \
  -d '{"creator_id":"demo-verified-user","verification_text":"ugh. long day. burned toast, missed class, spilled coffee on my notes, then laughed about it because what else was i gonna do?"}'
echo
echo

echo "== Appeal example =="
echo "Replace CONTENT_ID_HERE with a real content_id from a submit response."
curl -s -X POST "$BASE_URL/appeal" \
  -H "Content-Type: application/json" \
  -d '{"content_id":"CONTENT_ID_HERE","creator_reasoning":"I wrote this myself from personal experience."}'
echo
echo

echo "== Audit log =="
curl -s "$BASE_URL/log"
echo
echo

echo "== Dashboard =="
curl -s "$BASE_URL/dashboard"
echo
echo

echo "== Rate limit test =="
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE_URL/submit" \
    -H "Content-Type: application/json" \
    -d '{"text":"This is a test submission for rate limit testing purposes only.","creator_id":"ratelimit-demo"}'
done
