import json

import httpx
import pytest

from app.i18n.bhashini import BhashiniTranslator, TranslationError
from app.schemas.ask import AskRequest
from tests.conftest import FakeLLM

CONFIG = {
    "pipelineResponseConfig": [{"taskType": "translation", "config": [{"serviceId": "svc-1"}]}],
    "pipelineInferenceAPIEndPoint": {
        "callbackUrl": "https://infer.example/pipeline",
        "inferenceApiKey": {"name": "Authorization", "value": "infer-key"},
    },
}


def translator(settings, calls, target_text="translated"):
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("getModelsPipeline"):
            assert request.headers["ulcaApiKey"] == "k" and request.headers["userID"] == "u"
            return httpx.Response(200, json=CONFIG)
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "infer-key"
        assert body["pipelineTasks"][0]["config"]["serviceId"] == "svc-1"
        return httpx.Response(200, json={"pipelineResponse": [{"output": [{"target": target_text}]}]})

    s = settings.model_copy(
        update={"bhashini_user_id": "u", "bhashini_api_key": "k", "bhashini_pipeline_id": "p"}
    )
    return BhashiniTranslator(s, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_translate_caches_pipeline_config(settings):
    calls = []
    t = translator(settings, calls)
    assert await t.translate("வணக்கம்", "ta", "en") == "translated"
    assert await t.translate("நன்றி", "ta", "en") == "translated"
    assert len(calls) == 3  # one config call, two compute calls


async def test_same_language_is_a_no_op(settings):
    calls = []
    assert await translator(settings, calls).translate("hello", "en", "en") == "hello"
    assert calls == []


async def test_errors_raise_translation_error(settings):
    t = BhashiniTranslator(
        settings.model_copy(
            update={"bhashini_user_id": "u", "bhashini_api_key": "k", "bhashini_pipeline_id": "p"}
        ),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad key"))),
    )
    with pytest.raises(TranslationError):
        await t.translate("x", "ta", "en")


async def test_pipeline_translates_question_and_answer(make_pipeline, settings):
    calls = []
    t = translator(settings, calls, target_text="section 3(p) traditional knowledge patent")
    llm = FakeLLM()
    events = [e async for e in make_pipeline(llm, t).stream(AskRequest(query="தமிழ் கேள்வி", language="ta"))]
    assert not any(e["type"] == "delta" for e in events)  # translated answers arrive whole
    done = next(e for e in events if e["type"] == "done")
    assert done["generated_by"].endswith("+ bhashini")
    assert "section 3(p)" in llm.prompts[0][1]  # the model saw the English translation
