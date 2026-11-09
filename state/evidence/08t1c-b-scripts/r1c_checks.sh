set -u
cd /work
echo "## make lint"; make lint 2>&1 | tail -n 2
cd /work/backend
echo "## unit (quality, offline, 19, recognizers, 08t_ner, 18)"
pytest -q -p no:cacheprovider tests/unit/test_08t1c_7_ner_quality.py tests/unit/test_08t1c_12_offline_models_listed.py tests/unit/test_19_offline.py tests/unit/test_08_recognizers.py tests/unit/test_08t_ner.py tests/unit/test_08t_18_ner_candidates.py 2>&1 | tail -n 1
echo "## -m models (NER files; latency deselected)"
RUN_MODEL_TESTS=1 pytest -q -p no:cacheprovider -W ignore::DeprecationWarning -W ignore::UserWarning -m models tests/models/test_08t_ner_models.py tests/models/test_08t_ner_latency.py 2>&1 | tail -n 1
cd /work
echo "## verify.sh --models on the real (old) volume: expected FAIL naming savasy and the pickle"
MODELS_TXT=deploy/offline/models.txt bash deploy/offline/verify.sh --models /models | grep -v "^OK model "; echo "verify_exit=${PIPESTATUS[0]}"
echo "## packed tree (akdeniz27 rows only) loads offline"
grep -E "^hf akdeniz27/" deploy/offline/models.txt > /tmp/ner.txt
(cd /models && bash /work/deploy/offline/models-files.sh /tmp/ner.txt --root /models | tar --dereference -cf /tmp/ner.tar --files-from=-) && tar -tf /tmp/ner.tar
mkdir -p /tmp/loaded && tar -xf /tmp/ner.tar -C /tmp/loaded
MODELS_TXT=/tmp/ner.txt bash deploy/offline/verify.sh --models /tmp/loaded; echo "verify_packed_exit=$?"
cd backend && HF_HOME=/tmp/loaded/huggingface MODEL_CACHE_DIR=/tmp/loaded python -c "
from ffcore.guardrails.recognizers.ner import NerRecognizer
r = NerRecognizer.load('akdeniz27/bert-base-turkish-cased-ner', '99995f7d2be4b3a28c74f0d36ee97f8c04ee0571')
print('loaded from packed tree:', [(f.category, f.value) for f in r.recognize('Ayşe Demir arar.', {'PERSON'})])
" 2>&1 | grep -E "loaded from|Error|error" 
