"""
Script-to-Cinema: Orquestrador Principal
=========================================
Sistema automatizado para gerar vídeos bíblicos de alta qualidade
usando workflow LTX2 no ComfyUI.

Estrutura do Vídeo (4:30 min):
  00:00 - 00:30  → Trailer Hollywoodiano
  00:30 - 00:45  → Abertura do Canal
  00:45 - 04:15  → História Principal
  04:15 - 04:30  → Fechamento do Canal

Uso:
  python cinema_generator.py --theme "A Criação"
  python cinema_generator.py --queue-id 1
  python cinema_generator.py --full-pipeline
"""

import os
import sys
import json
import argparse
import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from supabase import create_client
except ImportError:
    create_client = None

# Módulos locais
from ltx2_workflow import LTX2WorkflowGenerator, VideoScene
from subtitle_generator import SubtitleGenerator
from youtube_uploader import YouTubeUploader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VideoStructure:
    """Estrutura do vídeo de 4:30 min."""
    trailer: Dict[str, Any]       # 00:00 - 00:30
    opening: Dict[str, Any]      # 00:30 - 00:45
    main_story: List[Dict]        # 00:45 - 04:15
    closing: Dict[str, Any]       # 04:15 - 04:30
    
    # Durações em segundos
    TRAILER_START = 0
    TRAILER_END = 30
    OPENING_START = 30
    OPENING_END = 45
    STORY_START = 45
    STORY_END = 255  # 4:15
    CLOSING_START = 255
    CLOSING_END = 270  # 4:30


# VideoScene importada de ltx2_workflow.py
# Estendemos com campos extras aqui
@dataclass
class VideoSceneExt:
    """Cena individual do vídeo (estendida)."""
    scene_number: int
    title: str
    prompt: str
    narration: str
    duration_seconds: int
    start_time: float
    scene_type: str  # trailer, opening, story, closing
    ltx2_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedVideo:
    """Vídeo completo gerado."""
    title: str
    theme: str
    source_url: str
    scenes: List[VideoScene]
    final_video_path: Path
    thumbnail_path: Optional[Path] = None
    subtitles_path: Optional[Path] = None
    youtube_url: Optional[str] = None
    video_id: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# GEMINI SCRIPT GENERATOR
# =============================================================================

class GeminiVideoScriptGenerator:
    """Gera roteiros de vídeo usando Google Gemini."""

    SYSTEM_PROMPT = """You are a master biblical video scriptwriter for cinematic productions.

Generate a complete script for a 4:30 minute biblical video with EXACT timing:

## TIMING STRUCTURE:
- 00:00 - 00:30 (30s): HOLLYWOOD TRAILER - High impact visuals, epic music cue
- 00:30 - 00:45 (15s): CHANNEL OPENING - Standard intro video
- 00:45 - 04:15 (3m30s): MAIN STORY - Sequential cinematic scenes
- 04:15 - 04:30 (15s): CHANNEL CLOSING - Standard outro video

## OUTPUT FORMAT (JSON ONLY):
{
  "title": "Video Title",
  "theme": "Biblical Theme",
  "trailer": {
    "prompt": "Epic cinematic prompt for trailer",
    "narration": "Narrator text for trailer",
    "duration": 30
  },
  "opening": {
    "video_path": "path/to/opening.mp4",
    "duration": 15
  },
  "story_scenes": [
    {
      "scene_number": 1,
      "title": "Scene Title",
      "prompt": "Cinematic prompt for LTX2",
      "narration": "Dialogue/narration text",
      "duration": 15,
      "scene_type": "cinematic"
    }
  ],
  "closing": {
    "video_path": "path/to/closing.mp4",
    "duration": 15
  }
}

## PROMPT REQUIREMENTS FOR LTX2:
Each prompt must include:
- Cinematic lighting (golden hour, dramatic shadows)
- Epic scale and composition
- Biblical atmosphere
- Camera movement hints (tracking, pan, zoom)
- Emotional tone

## STYLE: Cinematic Biblical Drama
- Aspect ratio: 16:9
- Quality: Cinematic 4K
- Lighting: Chiaroscuro with divine golden rays
- Mood: Epic, reverent, dramatic
"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        if genai is None:
            raise ImportError("google-generativeai required")
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def generate_script(self, theme: str) -> Dict[str, Any]:
        """Gera roteiro completo para o tema."""
        logger.info(f"Generating script for theme: {theme}")

        response = self.model.generate_content(
            contents=[{
                "role": "user",
                "parts": [{"text": f"{self.SYSTEM_PROMPT}\n\nGenerate script for: {theme}"}]
            }],
            generation_config={
                "temperature": 0.8,
                "max_output_tokens": 8192,
            }
        )

        # Parse JSON
        text = response.text
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)


# =============================================================================
# SUPABASE QUEUE MANAGER
# =============================================================================

class VideoQueueManager:
    """Gerencia fila de vídeos no Supabase."""

    def __init__(self, url: str, key: str):
        if create_client is None:
            raise ImportError("supabase required")
        self.client = create_client(url, key)

    def get_next_pending(self) -> Optional[Dict]:
        """Busca próximo vídeo pendente."""
        response = self.client.table("video_queue").select("*").eq(
            "status", "pending"
        ).order("priority", desc=True).order("created_at").limit(1).execute()

        if not response.data:
            return None
        return response.data[0]

    def update_status(self, item_id: int, status: str, metadata: Dict = None):
        """Atualiza status do item."""
        updates = {"status": status, "updated_at": datetime.now().isoformat()}
        if metadata:
            updates["metadata"] = metadata

        self.client.table("video_queue").update(updates).eq("id", item_id).execute()

    def add_to_queue(
        self,
        theme: str,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        priority: int = 0
    ) -> Dict:
        """Adiciona tema à fila."""
        data = {
            "theme": theme,
            "title": title,
            "source_url": source_url,
            "status": "pending",
            "priority": priority,
            "metadata": {}
        }
        response = self.client.table("video_queue").insert(data).execute()
        return response.data[0]

    def get_queue_status(self) -> Dict[str, int]:
        """Retorna contagem por status."""
        response = self.client.table("video_queue").select("status").execute()
        counts = {"pending": 0, "processing": 0, "rendering": 0, "completed": 0, "failed": 0}
        for item in response.data:
            status = item.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts


# =============================================================================
# CINEMA GENERATOR (MAIN ORCHESTRATOR)
# =============================================================================

class CinemaGenerator:
    """Orquestrador principal do sistema Script-to-Cinema."""

    def __init__(
        self,
        gemini_api_key: str,
        supabase_url: str,
        supabase_key: str,
        output_dir: Path = Path("./output"),
        comfyui_url: str = "http://127.0.0.1:8181"
    ):
        self.gemini_api_key = gemini_api_key
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.output_dir = output_dir
        self.comfyui_url = comfyui_url

        # Criar diretórios
        self.scenes_dir = output_dir / "scenes"
        self.videos_dir = output_dir / "videos"
        self.subtitles_dir = output_dir / "subtitles"
        self.thumbnails_dir = output_dir / "thumbnails"

        for d in [self.scenes_dir, self.videos_dir, self.subtitles_dir, self.thumbnails_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Inicializar gerenciadores
        self.queue_manager = VideoQueueManager(supabase_url, supabase_key)
        self.script_generator = GeminiVideoScriptGenerator(gemini_api_key)
        self.workflow_generator = LTX2WorkflowGenerator(comfyui_url)
        self.subtitle_generator = SubtitleGenerator()
        self.youtube_uploader = YouTubeUploader()

    def generate_video(self, theme: str, queue_item_id: Optional[int] = None) -> GeneratedVideo:
        """
        Função PRINCIPAL: Gera vídeo completo.

        Args:
            theme: Tema bíblico
            queue_item_id: ID do item na fila

        Returns:
            GeneratedVideo com todos os dados
        """
        logger.info("=" * 60)
        logger.info(f"GENERATING VIDEO: {theme}")
        logger.info("=" * 60)

        # 1. Gerar roteiro com Gemini
        logger.info("[1/6] Generating script with Gemini...")
        script_data = self.script_generator.generate_script(theme)

        title = script_data.get("title", f"Biblical Cinema: {theme}")

        # 2. Preparar cenas para renderização
        logger.info("[2/6] Preparing scenes for LTX2...")
        scenes = self._prepare_scenes(script_data)

        # 3. Renderizar cenas no Kaggle/ComfyUI
        logger.info("[3/6] Rendering scenes with LTX2...")
        rendered_videos = self._render_scenes(scenes, queue_item_id)

        # 4. Juntar com FFmpeg
        logger.info("[4/6] Assembling video with FFmpeg...")
        final_video = self._assemble_video(rendered_videos, title)

        # 5. Gerar legendas
        logger.info("[5/6] Generating subtitles...")
        subtitles_path = self._generate_subtitles(scenes, title)

        # 6. Upload para YouTube
        logger.info("[6/6] Uploading to YouTube...")
        youtube_result = self._upload_to_youtube(final_video, title, script_data)

        return GeneratedVideo(
            title=title,
            theme=theme,
            source_url=script_data.get("source_url", ""),
            scenes=scenes,
            final_video_path=final_video,
            subtitles_path=subtitles_path,
            youtube_url=youtube_result.get("url"),
            video_id=youtube_result.get("id")
        )

    def _prepare_scenes(self, script_data: Dict) -> List[VideoScene]:
        """Prepara lista de cenas do roteiro."""
        scenes = []
        current_time = 0.0

        # Trailer
        trailer = script_data.get("trailer", {})
        scenes.append(VideoScene(
            scene_number=0,
            title="Trailer",
            prompt=trailer.get("prompt", ""),
            narration=trailer.get("narration", ""),
            duration_seconds=30,
            start_time=current_time,
            scene_type="trailer"
        ))
        current_time += 30

        # Story scenes
        for i, scene_data in enumerate(script_data.get("story_scenes", [])):
            duration = scene_data.get("duration", 15)
            scenes.append(VideoScene(
                scene_number=i + 1,
                title=scene_data.get("title", f"Scene {i+1}"),
                prompt=scene_data.get("prompt", ""),
                narration=scene_data.get("narration", ""),
                duration_seconds=duration,
                start_time=current_time,
                scene_type="story"
            ))
            current_time += duration

        return scenes

    def _render_scenes(
        self,
        scenes: List[VideoScene],
        queue_item_id: Optional[int]
    ) -> List[Path]:
        """Renderiza todas as cenas usando LTX2."""
        rendered = []

        for scene in scenes:
            logger.info(f"Rendering scene {scene.scene_number}: {scene.title}")

            # Atualizar status se tiver queue_id
            if queue_item_id:
                self.queue_manager.update_status(
                    queue_item_id,
                    "rendering",
                    {"current_scene": scene.scene_number}
                )

            # Gerar vídeo com LTX2
            output_path = self.scenes_dir / f"scene_{scene.scene_number:02d}.mp4"

            success = self.workflow_generator.render_scene(
                prompt=scene.prompt,
                output_path=output_path,
                duration=scene.duration_seconds,
                scene_type=scene.scene_type
            )

            if success:
                rendered.append(output_path)
            else:
                logger.warning(f"Failed scene {scene.scene_number}, using placeholder")

        return rendered

    def _assemble_video(self, scenes: List[Path], title: str) -> Path:
        """Junta todas as cenas em um único vídeo."""
        final_path = self.videos_dir / f"{title.replace(' ', '_')}_final.mp4"

        # Criar arquivo de lista para FFmpeg
        list_file = self.videos_dir / "concat_list.txt"
        with open(list_file, 'w') as f:
            for scene_path in scenes:
                f.write(f"file '{scene_path.absolute()}'\n")

        # Concatenar com FFmpeg
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "medium",
            "-crf", "23", "-c:a", "aac", "-b:a", "128k",
            str(final_path)
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr.decode()}")

        return final_path

    def _generate_subtitles(self, scenes: List[VideoScene], title: str) -> Path:
        """Gera legendas para todas as cenas."""
        subtitles_path = self.subtitles_dir / f"{title.replace(' ', '_')}.srt"

        self.subtitle_generator.create_subtitles(
            scenes=scenes,
            output_path=subtitles_path
        )

        return subtitles_path

    def _upload_to_youtube(
        self,
        video_path: Path,
        title: str,
        script_data: Dict
    ) -> Dict:
        """Faz upload do vídeo para o YouTube."""
        # Gerar metadados
        description = self._generate_description(script_data)
        tags = self._generate_tags(script_data)

        result = self.youtube_uploader.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=None  # Pode gerar thumbnail depois
        )

        return result

    def _generate_description(self, script_data: Dict) -> str:
        """Gera descrição otimizada para SEO."""
        theme = script_data.get("theme", "")
        return f"""📖 {script_data.get('title', 'Biblical Cinema')}

Uma jornada cinematográfica pelos sagrados textos bíblicos.

🌟 Neste vídeo:
Uma experiência visual épica que traz à vida momentos bíblicos fundamentais.

📚 Referências:
- Gênesis, Êxodo, Salmos e muito mais

🔔 INSCREVA-SE para mais conteúdo bíblico!

#bíblia #biblico #cristão #fé #deo #igreja #video #cinema #epico
"""

    def _generate_tags(self, script_data: Dict) -> List[str]:
        """Gera tags estratégicas."""
        base_tags = [
            "bíblia", "biblico", "cristão", "fé", "deus",
            "video bíblico", "história bíblica", "cinema",
            "epic", "narrativa", "sagrado", "religioso"
        ]

        theme_tags = script_data.get("theme", "").lower().split()
        return base_tags + theme_tags


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def generate_video_with_ltx2(
    theme: str,
    gemini_api_key: str,
    supabase_url: str,
    supabase_key: str,
    output_dir: Optional[Path] = None
) -> Optional[GeneratedVideo]:
    """
    Função principal para ser chamada pelo GitHub Actions.

    Args:
        theme: Tema bíblico
        gemini_api_key: Chave da API Gemini
        supabase_url: URL do Supabase
        supabase_key: Chave do Supabase
        output_dir: Diretório de saída

    Returns:
        GeneratedVideo ou None se não houver temas
    """
    logger.info("=" * 60)
    logger.info("SCRIPT-TO-CINEMA: LTX2 Video Generator")
    logger.info("=" * 60)

    output_dir = output_dir or Path("./output")
    generator = CinemaGenerator(
        gemini_api_key=gemini_api_key,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        output_dir=output_dir
    )

    # Se theme fornecido, gerar diretamente
    if theme:
        return generator.generate_video(theme)

    # Buscar da fila
    queue_item = generator.queue_manager.get_next_pending()
    if not queue_item:
        logger.info("No pending items in queue")
        return None

    # Atualizar status
    queue_item_id = queue_item["id"]
    generator.queue_manager.update_status(queue_item_id, "processing")

    try:
        video = generator.generate_video(
            theme=queue_item["theme"],
            queue_item_id=queue_item_id
        )

        # Marcar como completo
        generator.queue_manager.update_status(
            queue_item_id,
            "completed",
            {
                "youtube_url": video.youtube_url,
                "youtube_id": video.video_id,
                "video_path": str(video.final_video_path)
            }
        )

        return video

    except Exception as e:
        logger.error(f"Failed to generate video: {e}")
        generator.queue_manager.update_status(
            queue_item_id,
            "failed",
            {"error": str(e)}
        )
        raise


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Script-to-Cinema: LTX2 Video Generator")
    parser.add_argument("--theme", help="Biblical theme for video")
    parser.add_argument("--queue-id", type=int, help="Process specific queue item")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--skip-youtube", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--list-queue", action="store_true", help="Show queue status")

    args = parser.parse_args()

    # Carregar env vars
    gemini_key = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "YOUR_ANON_KEY")
    output_dir = Path(args.output_dir)

    if args.list_queue:
        manager = VideoQueueManager(supabase_url, supabase_key)
        status = manager.get_queue_status()
        print("Video Queue Status:")
        for s, count in status.items():
            print(f"  {s}: {count}")
        return

    if args.theme:
        video = generate_video_with_ltx2(
            theme=args.theme,
            gemini_api_key=gemini_key,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            output_dir=output_dir
        )
        if video:
            print(f"Video generated: {video.final_video_path}")
            if video.youtube_url:
                print(f"YouTube: {video.youtube_url}")
        return

    # Processar fila
    video = generate_video_with_ltx2(
        theme=None,
        gemini_api_key=gemini_key,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        output_dir=output_dir
    )

    if video:
        print(f"Video generated: {video.final_video_path}")
    else:
        print("No videos to process")


if __name__ == "__main__":
    main()
