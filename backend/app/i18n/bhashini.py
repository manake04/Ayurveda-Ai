"""Translation through Bhashini (National Language Translation Mission), ULCA pipeline API.

Two calls, as documented by Bhashini:
1. Pipeline config (`getModelsPipeline`, authenticated with userID + ulcaApiKey) returns
   the inference endpoint, its API key, and the serviceId for a language pair. Cached.
2. Compute call to that endpoint with a `translation` task.

Only active when BHASHINI_USER_ID, BHASHINI_API_KEY and BHASHINI_PIPELINE_ID are set.
Tested against mocked responses; verify with real credentials before relying on it.
"""

import httpx

from app.core.config import Settings


class TranslationError(RuntimeError):
    pass


class BhashiniTranslator:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._settings = settings
        self._client = client
        self._configs: dict[tuple[str, str], tuple[str, dict, str]] = {}

    async def _config(self, source: str, target: str) -> tuple[str, dict, str]:
        """(callback url, auth header, serviceId) for a language pair."""
        key = (source, target)
        if key not in self._configs:
            s = self._settings
            resp = await self._client.post(
                s.bhashini_config_url,
                headers={"userID": s.bhashini_user_id, "ulcaApiKey": s.bhashini_api_key},
                json={
                    "pipelineTasks": [
                        {
                            "taskType": "translation",
                            "config": {"language": {"sourceLanguage": source, "targetLanguage": target}},
                        }
                    ],
                    "pipelineRequestConfig": {"pipelineId": s.bhashini_pipeline_id},
                },
                timeout=20,
            )
            if resp.status_code != 200:
                raise TranslationError(f"Bhashini config failed: HTTP {resp.status_code} {resp.text[:200]}")
            body = resp.json()
            endpoint = body["pipelineInferenceAPIEndPoint"]
            auth = endpoint["inferenceApiKey"]
            service_id = body["pipelineResponseConfig"][0]["config"][0]["serviceId"]
            self._configs[key] = (endpoint["callbackUrl"], {auth["name"]: auth["value"]}, service_id)
        return self._configs[key]

    async def translate(self, text: str, source: str, target: str) -> str:
        if source == target or not text.strip():
            return text
        try:
            url, headers, service_id = await self._config(source, target)
            resp = await self._client.post(
                url,
                headers=headers,
                json={
                    "pipelineTasks": [
                        {
                            "taskType": "translation",
                            "config": {
                                "language": {"sourceLanguage": source, "targetLanguage": target},
                                "serviceId": service_id,
                            },
                        }
                    ],
                    "inputData": {"input": [{"source": text}]},
                },
                timeout=30,
            )
            if resp.status_code != 200:
                raise TranslationError(
                    f"Bhashini translation failed: HTTP {resp.status_code} {resp.text[:200]}"
                )
            return resp.json()["pipelineResponse"][0]["output"][0]["target"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise TranslationError(f"Bhashini translation failed: {exc!r}") from exc
