#!/usr/bin/env bash
set -euo pipefail

# Smoke test for documents endpoint
# Uses Backboard API directly to narrow down where the problem is

API_KEY="${BACKBOARD_API_KEY:?Set BACKBOARD_API_KEY}"
BB_URL="https://app.backboard.io/api"

echo "=== Step 1: List assistants (first 3) ==="
status="$(curl -sS -o /tmp/smoke_assistants.json -w "%{http_code}" \
  -H "X-API-Key: ${API_KEY}" \
  "${BB_URL}/assistants?skip=0&limit=3")"

if [[ "${status}" != "200" ]]; then
  echo "FAIL: GET /assistants returned ${status}"
  cat /tmp/smoke_assistants.json
  exit 1
fi

echo "PASS: GET /assistants returned 200"
echo "Response (first 500 chars):"
head -c 500 /tmp/smoke_assistants.json
echo ""

# Count assistants returned
ASST_COUNT=$(python3 -c "import json; data=json.load(open('/tmp/smoke_assistants.json')); print(len(data))")
echo "Assistants in batch: ${ASST_COUNT}"

if [[ "${ASST_COUNT}" == "0" ]]; then
  echo "FAIL: No assistants returned"
  exit 1
fi

# Get first assistant id
FIRST_AID=$(python3 -c "
import json
data = json.load(open('/tmp/smoke_assistants.json'))
item = data[0]
# SDK returns assistant_id
aid = item.get('assistant_id') or item.get('id') or ''
print(aid)
")
echo "First assistant ID: ${FIRST_AID}"

echo ""
echo "=== Step 2: List documents for first assistant ==="
status="$(curl -sS -o /tmp/smoke_docs1.json -w "%{http_code}" \
  -H "X-API-Key: ${API_KEY}" \
  "${BB_URL}/assistants/${FIRST_AID}/documents")"

echo "GET /assistants/${FIRST_AID}/documents returned ${status}"
echo "Response:"
cat /tmp/smoke_docs1.json
echo ""

echo ""
echo "=== Step 3: Try all 3 assistants and count docs ==="
TOTAL_DOCS=0
for i in 0 1 2; do
  AID=$(python3 -c "
import json
data = json.load(open('/tmp/smoke_assistants.json'))
if $i < len(data):
    item = data[$i]
    print(item.get('assistant_id') or item.get('id') or '')
else:
    print('')
")
  if [[ -z "${AID}" ]]; then continue; fi

  status="$(curl -sS -o /tmp/smoke_docs_${i}.json -w "%{http_code}" \
    -H "X-API-Key: ${API_KEY}" \
    "${BB_URL}/assistants/${AID}/documents")"

  if [[ "${status}" == "200" ]]; then
    COUNT=$(python3 -c "import json; data=json.load(open('/tmp/smoke_docs_${i}.json')); print(len(data))")
    echo "  Assistant ${AID}: ${COUNT} docs (HTTP ${status})"
    TOTAL_DOCS=$((TOTAL_DOCS + COUNT))
  else
    echo "  Assistant ${AID}: HTTP ${status}"
    head -c 200 /tmp/smoke_docs_${i}.json
    echo ""
  fi
done
echo "Total docs found across 3 assistants: ${TOTAL_DOCS}"

echo ""
echo "=== Step 4: Check SDK Document shape ==="
echo "First doc response shape (if any):"
python3 -c "
import json, sys
for i in range(3):
    try:
        data = json.load(open(f'/tmp/smoke_docs_{i}.json'))
        if data and isinstance(data, list) and len(data) > 0:
            doc = data[0]
            print(f'  Keys: {list(doc.keys())}')
            print(f'  Full doc: {json.dumps(doc, indent=2, default=str)}')
            sys.exit(0)
    except: pass
print('  No documents found in any of the 3 assistants')
"

echo ""
echo "=== Step 5: Scan for assistants WITH documents (first 20) ==="
status="$(curl -sS -o /tmp/smoke_assistants20.json -w "%{http_code}" \
  -H "X-API-Key: ${API_KEY}" \
  "${BB_URL}/assistants?skip=0&limit=20")"

if [[ "${status}" == "200" ]]; then
  python3 -c "
import json, subprocess, sys

assistants = json.load(open('/tmp/smoke_assistants20.json'))
print(f'Checking {len(assistants)} assistants for docs...')
found = 0
for asst in assistants:
    aid = asst.get('assistant_id') or asst.get('id') or ''
    name = asst.get('name', 'unnamed')
    if not aid: continue
    import urllib.request
    req = urllib.request.Request(
        f'https://app.backboard.io/api/assistants/{aid}/documents',
        headers={'X-API-Key': '${API_KEY}'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            docs = json.loads(resp.read())
            if docs:
                found += 1
                print(f'  FOUND {len(docs)} docs in: {name} ({aid})')
                if found == 1:
                    print(f'    Doc keys: {list(docs[0].keys())}')
    except Exception as e:
        print(f'  Error for {name}: {e}')
if found == 0:
    print('  No docs found in first 20 assistants')
print(f'Assistants with docs: {found}/20')
"
fi

echo ""
echo "Smoke test complete."
