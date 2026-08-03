import asyncio
import base64
import html
from io import BytesIO
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential
from openai import AsyncOpenAI
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .config import Settings
from .models import Artifact, ResearchResult


class ArtifactGenerator:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._credential: DefaultAzureCredential | None = None

    @property
    def credential(self) -> DefaultAzureCredential:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    async def generate(self, run_id: str, result: ResearchResult) -> list[Artifact]:
        run_dir = self._settings.artifacts_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        chart = await self._write_chart(run_dir, result)
        image = await self._generate_image(run_dir)
        audio = await self._generate_speech(run_dir, result.highlighted_chapter)
        pdf = await asyncio.to_thread(self._write_pdf, run_dir, result)
        return [
            self._artifact(chart, "chart", "image/svg+xml"),
            self._artifact(image, "image", "image/png"),
            self._artifact(audio, "audio", "audio/wav"),
            self._artifact(pdf, "report", "application/pdf"),
        ]

    def _artifact(self, path: Path, kind: str, content_type: str) -> Artifact:
        return Artifact(
            name=path.name,
            kind=kind,
            url=f"/api/runs/{path.parent.name}/artifacts/{path.name}",
            content_type=content_type,
            bytes=path.stat().st_size,
        )

    async def _write_chart(self, run_dir: Path, result: ResearchResult) -> Path:
        scores = result.service_scores or {
            "Commercial banking": 88,
            "Investment services": 82,
            "Compliance automation": 91,
            "Fraud prevention": 94,
        }
        width, height = 900, 420
        bars = []
        for index, (label, score) in enumerate(scores.items()):
            y = 76 + index * 78
            bar_width = int(620 * min(max(score, 0), 100) / 100)
            bars.append(
                f'<text x="42" y="{y}" class="label">{html.escape(label)}</text>'
                f'<rect x="238" y="{y - 24}" width="620" height="30" rx="8" '
                f'fill="#e7e8e3"/><rect x="238" y="{y - 24}" width="{bar_width}" '
                f'height="30" rx="8" fill="#c7ff5e"/>'
                f'<text x="870" y="{y}" text-anchor="end" class="score">{score:.0f}</text>'
            )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}"><style>'
            ".title{font:700 28px Arial;fill:#142116}.label{font:600 17px Arial;"
            "fill:#142116}.score{font:700 18px Arial;fill:#142116}</style>"
            '<rect width="100%" height="100%" rx="24" fill="#f7f8f3"/>'
            '<text x="42" y="40" class="title">Priority service portfolio</text>'
            + "".join(bars)
            + "</svg>"
        )
        path = run_dir / "service-priorities.svg"
        path.write_text(svg, encoding="utf-8")
        return path

    async def _generate_image(self, run_dir: Path) -> Path:
        if not self._settings.image_model_endpoint:
            raise RuntimeError(
                "IMAGE_MODEL_ENDPOINT is not configured for live FLUX output."
            )
        token = await asyncio.to_thread(
            self.credential.get_token,
            "https://cognitiveservices.azure.com/.default",
        )
        client = AsyncOpenAI(
            api_key=token.token,
            base_url=(
                f"{self._settings.image_model_endpoint.rstrip('/')}/openai/v1/"
            ),
            default_query={"api-version": "preview"},
        )
        response = await client.images.generate(
            model=self._settings.image_model_deployment,
            prompt=(
                "Editorial hero image for a premium global investment bank near the "
                "Texas Stock Exchange in Dallas. Modern architecture, subtle market "
                "data motifs, trustworthy human-centered financial services, no text, "
                "deep forest green and electric chartreuse accents."
            ),
            size="1440x960",
        )
        path = run_dir / "bank-hero.png"
        generated = response.data[0]
        if generated.b64_json:
            image_bytes = base64.b64decode(generated.b64_json)
        elif generated.url:
            async with httpx.AsyncClient(timeout=60) as http:
                download = await http.get(generated.url)
                download.raise_for_status()
            image_bytes = download.content
        else:
            raise RuntimeError("FLUX-1.1-pro returned no image data.")
        with Image.open(BytesIO(image_bytes)) as image:
            image.convert("RGB").save(path, format="PNG")
        return path

    async def _generate_speech(self, run_dir: Path, text: str) -> Path:
        if not self._settings.speech_region or not self._settings.speech_resource_id:
            raise RuntimeError(
                "SPEECH_REGION and SPEECH_RESOURCE_ID are required for live narration."
            )
        token = await asyncio.to_thread(
            self.credential.get_token,
            "https://cognitiveservices.azure.com/.default",
        )
        authorization = (
            f"Bearer aad#{self._settings.speech_resource_id}#{token.token}"
        )
        ssml = (
            '<speak version="1.0" xml:lang="en-US">'
            f'<voice name="{html.escape(self._settings.speech_voice)}">'
            f"{html.escape(text[:8000])}</voice></speak>"
        )
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://"
                f"{self._settings.speech_region}.tts.speech.microsoft.com/"
                "cognitiveservices/v1",
                headers={
                    "Authorization": authorization,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                    "User-Agent": "gartner-foundry-demo",
                },
                content=ssml.encode("utf-8"),
            )
        response.raise_for_status()
        if not response.content:
            raise RuntimeError("Azure Speech returned an empty audio response.")
        path = run_dir / "services-narration.wav"
        path.write_bytes(response.content)
        return path

    def _write_pdf(self, run_dir: Path, result: ResearchResult) -> Path:
        path = run_dir / "bank-strategy-report.pdf"
        styles = getSampleStyleSheet()
        story = [
            Paragraph("Global Bank Strategy: Deep Research Report", styles["Title"]),
            Spacer(1, 18),
        ]
        for block in result.report_markdown.split("\n\n"):
            clean = html.escape(block.strip()).replace("\n", "<br/>")
            if clean:
                story.append(Paragraph(clean, styles["BodyText"]))
                story.append(Spacer(1, 10))
        story.extend(
            [
                PageBreak(),
                Paragraph("Recommended Banking Services", styles["Heading1"]),
                Paragraph(
                    html.escape(result.highlighted_chapter).replace("\n", "<br/>"),
                    styles["BodyText"],
                ),
                PageBreak(),
                Paragraph("Sources", styles["Heading1"]),
            ]
        )
        for citation in result.citations:
            story.append(
                Paragraph(
                    f"[{citation.id}] {html.escape(citation.title)} - "
                    f"{html.escape(str(citation.url))}",
                    styles["BodyText"],
                )
            )
        SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        ).build(story)
        return path
