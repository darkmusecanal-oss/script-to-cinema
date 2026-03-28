"""
YouTube Uploader
================
Upload automático de vídeos para YouTube via API v3.
Inclui geração de thumbnail, título e descrição otimizados.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.discovery import build
except ImportError:
    Credentials = None
    build = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VideoMetadata:
    """Metadados do vídeo para upload."""
    title: str
    description: str
    tags: List[str]
    category_id: str = "22"  # People & Blogs
    privacy_status: str = "public"  # public, private, unlisted
    thumbnail_path: Optional[Path] = None
    playlist_id: Optional[str] = None


@dataclass
class UploadResult:
    """Resultado do upload."""
    success: bool
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# YOUTUBE UPLOADER (OAuth2 + Refresh Token)
# =============================================================================

class YouTubeUploader:
    """Upload de vídeos para YouTube via OAuth2."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        # Legacy support
        credentials_path: Optional[str] = None,
        service_account_json: Optional[Dict] = None
    ):
        """
        Inicializa o uploader com OAuth2.

        Args:
            client_id: Google OAuth Client ID
            client_secret: Google OAuth Client Secret
            refresh_token: OAuth Refresh Token
        """
        self.client_id = client_id or os.getenv("YOUTUBE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("YOUTUBE_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or os.getenv("YOUTUBE_REFRESH_TOKEN", "")
        self.youtube = None

        if build is None:
            logger.warning("google-api-python-client not installed")

    def authenticate(self) -> bool:
        """Autentica com a API do YouTube via OAuth2 Refresh Token."""
        if build is None:
            logger.error("google-api-python-client required")
            return False

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.error("Missing OAuth credentials (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)")
            return False

        try:
            credentials = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=[
                    'https://www.googleapis.com/auth/youtube.upload',
                    'https://www.googleapis.com/auth/youtube'
                ]
            )

            # Renovar token
            credentials.refresh(Request())
            logger.info("YouTube OAuth token refreshed successfully")

            self.youtube = build('youtube', 'v3', credentials=credentials)
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        category_id: str = "22",
        privacy_status: str = "public",
        thumbnail_path: Optional[Path] = None,
        playlist_id: Optional[str] = None
    ) -> UploadResult:
        """
        Faz upload de vídeo para o YouTube.

        Args:
            video_path: Path do arquivo de vídeo
            title: Título do vídeo
            description: Descrição
            tags: Tags (máximo 500 caracteres)
            category_id: ID da categoria
            privacy_status: public, private, ou unlisted
            thumbnail_path: Path da thumbnail (opcional)
            playlist_id: ID da playlist (opcional)

        Returns:
            UploadResult com dados do vídeo
        """
        if not self.youtube and not self.authenticate():
            return UploadResult(success=False, error="Authentication failed")

        if not video_path.exists():
            return UploadResult(success=False, error=f"File not found: {video_path}")

        try:
            # Preparar tags
            if tags:
                # YouTube limite: 500 caracteres para tags
                tags_str = ",".join(tags[:15])  # Máximo 15 tags
            else:
                tags_str = ""

            # Criar body do request
            body = {
                "snippet": {
                    "title": self._truncate_title(title),
                    "description": description[:5000],  # Limite 5000 chars
                    "tags": tags,
                    "categoryId": category_id,
                    "defaultLanguage": "pt_BR",
                    "localized": {
                        "title": title[:100],
                        "description": description[:5000]
                    }
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                    "publicStatsViewable": True
                },
                "recordingDate": datetime.now().isoformat() + "Z"
            }

            # Upload do vídeo
            media = MediaFileUpload(
                str(video_path),
                chunksize=-1,
                resumable=True
            )

            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            logger.info(f"Uploading video: {title}")
            response = self._upload_with_progress(request)

            if not response:
                return UploadResult(success=False, error="Upload failed")

            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            # Upload thumbnail se fornecida
            thumbnail_url = None
            if thumbnail_path and thumbnail_path.exists():
                thumbnail_url = self._upload_thumbnail(video_id, thumbnail_path)

            # Adicionar à playlist se fornecida
            if playlist_id:
                self._add_to_playlist(video_id, playlist_id)

            logger.info(f"Upload complete: {video_url}")

            return UploadResult(
                success=True,
                video_id=video_id,
                video_url=video_url,
                thumbnail_url=thumbnail_url
            )

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return UploadResult(success=False, error=str(e))

    def upload_with_thumbnail(
        self,
        video_path: Path,
        thumbnail_path: Path,
        **kwargs
    ) -> UploadResult:
        """Upload com thumbnail gerada automaticamente."""
        return self.upload(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            **kwargs
        )

    def _upload_with_progress(self, request) -> Optional[Dict]:
        """Upload com barra de progresso."""
        try:
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")

            return response

        except Exception as e:
            logger.error(f"Chunk upload error: {e}")
            return None

    def _upload_thumbnail(self, video_id: str, thumbnail_path: Path) -> Optional[str]:
        """Faz upload da thumbnail."""
        try:
            thumbnail = MediaFileUpload(str(thumbnail_path))

            response = self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumbnail
            ).execute()

            if response.get('items'):
                return response['items'][0]['default']['url']

        except Exception as e:
            logger.warning(f"Thumbnail upload failed: {e}")

        return None

    def _add_to_playlist(self, video_id: str, playlist_id: str) -> bool:
        """Adiciona vídeo a uma playlist."""
        try:
            self.youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            return True

        except Exception as e:
            logger.warning(f"Playlist add failed: {e}")
            return False

    def _truncate_title(self, title: str) -> str:
        """Trunca título para limite do YouTube."""
        if len(title) > 100:
            return title[:97] + "..."
        return title

    def update_video(
        self,
        video_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy_status: Optional[str] = None
    ) -> bool:
        """Atualiza metadados de vídeo existente."""
        if not self.youtube and not self.authenticate():
            return False

        try:
            update_body = {"id": video_id}
            update_parts = []

            if title or description:
                snippet = {}
                if title:
                    snippet["title"] = self._truncate_title(title)
                if description:
                    snippet["description"] = description[:5000]
                if tags:
                    snippet["tags"] = tags
                update_body["snippet"] = snippet
                update_parts.append("snippet")

            if privacy_status:
                update_body["status"] = {"privacyStatus": privacy_status}
                update_parts.append("status")

            self.youtube.videos().update(
                part=",".join(update_parts),
                body=update_body
            ).execute()

            return True

        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """Obtém informações de um vídeo."""
        if not self.youtube and not self.authenticate():
            return None

        try:
            response = self.youtube.videos().list(
                part="snippet,statistics,status",
                id=video_id
            ).execute()

            if response.get('items'):
                return response['items'][0]

        except Exception as e:
            logger.error(f"Get info failed: {e}")

        return None


# =============================================================================
# THUMBNAIL GENERATOR
# =============================================================================

class ThumbnailGenerator:
    """Gera thumbnails automaticamente."""

    def __init__(self, output_dir: Path = Path("./thumbnails")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_video(
        self,
        video_path: Path,
        timestamp_seconds: float = 1.0,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Extrai thumbnail de um frame do vídeo.

        Args:
            video_path: Path do vídeo
            timestamp_seconds: Timestamp do frame
            output_name: Nome do arquivo de saída

        Returns:
            Path da thumbnail gerada
        """
        if output_name is None:
            output_name = f"{video_path.stem}_thumb.jpg"

        output_path = self.output_dir / output_name

        # Usar FFmpeg para extrair frame
        import subprocess

        cmd = [
            "ffmpeg", "-y", "-ss", str(timestamp_seconds),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",  # Qualidade
            "-vf", "scale=1280:720",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            return output_path

        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode()}")

    def enhance_thumbnail(
        self,
        input_path: Path,
        title: str,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Adiciona texto/title à thumbnail.

        Args:
            input_path: Path da imagem
            title: Título para adicionar
            output_name: Nome de saída

        Returns:
            Path da thumbnail processada
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Carregar imagem
            img = Image.open(input_path)

            # Adicionar overlay escuro
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Gradiente escuro na parte inferior
            for i in range(img.height // 2, img.height):
                alpha = int(((i - img.height // 2) / (img.height // 2)) * 180)
                draw.rectangle([(0, i), (img.width, i + 1)], fill=(0, 0, 0, alpha))

            img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

            # Adicionar texto
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 48)
            except:
                font = ImageFont.load_default()

            # Texto centralizado
            text_bbox = draw.textbbox((0, 0), title, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (img.width - text_width) // 2
            y = img.height - text_height - 40

            # Sombra
            draw.text((x + 2, y + 2), title, font=font, fill=(0, 0, 0))
            # Texto principal (amarelo/dourado para Bíblico)
            draw.text((x, y), title, font=font, fill=(255, 215, 0))

            # Salvar
            if output_name is None:
                output_name = f"{input_path.stem}_title.jpg"

            output_path = self.output_dir / output_name
            img.save(output_path, quality=95)

            return output_path

        except ImportError:
            logger.warning("Pillow not installed, returning original")
            return input_path


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Exemplo de upload (OAuth2)
    uploader = YouTubeUploader(
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN")
    )

    result = uploader.upload(
        video_path=Path("./output/video.mp4"),
        title="A Criação - Filme Bíblico Completo",
        description="Um épico cinematográfico da criação segundo Gênesis...",
        tags=["bíblia", "criação", "filme bíblico", "gênesis"],
        privacy_status="public"
    )

    if result.success:
        print(f"Uploaded: {result.video_url}")
    else:
        print(f"Failed: {result.error}")
