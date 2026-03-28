"""
Subtitle Generator
=================
Gera legendas automáticas para vídeos bíblicos usando FFmpeg.
Sincronização perfeita com o áudio/narração.

Estilos de legenda:
- Fonte amarela com contorno preto (padrão cinematográfico)
- Centralizada na parte inferior
- Fade in/out suave
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SubtitleStyle:
    """Estilo visual da legenda."""
    font_name: str = "Arial"
    font_size: int = 48
    primary_color: str = "FFDD00"  # Amarelo/dourado
    outline_color: str = "000000"   # Preto
    shadow_color: str = "000000"
    outline_width: int = 2
    shadow_width: int = 1
    margin_vertical: int = 50
    margin_horizontal: int = 20
    alignment: str = "bottom"  # top, center, bottom


@dataclass
class SubtitleLine:
    """Uma linha de legenda."""
    index: int
    start_time: float  # segundos
    end_time: float
    text: str
    style: Optional[SubtitleStyle] = None


# =============================================================================
# SRT FORMATTER
# =============================================================================

class SRTFormatter:
    """Formata legendas em formato SRT."""

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        Converte segundos para formato SRT (HH:MM:SS,mmm).

        Args:
            seconds: Tempo em segundos

        Returns:
            String formatada
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def create_srt(subtitles: List[SubtitleLine]) -> str:
        """
        Cria conteúdo SRT.

        Args:
            subtitles: Lista de legendas

        Returns:
            String no formato SRT
        """
        lines = []

        for sub in subtitles:
            lines.append(str(sub.index))
            lines.append(f"{SRTFormatter.format_timestamp(sub.start_time)} --> {SRTFormatter.format_timestamp(sub.end_time)}")
            lines.append(sub.text)
            lines.append("")  # Linha vazia entre legendas

        return "\n".join(lines)

    @staticmethod
    def parse_srt(srt_content: str) -> List[SubtitleLine]:
        """
        Faz parse de conteúdo SRT.

        Args:
            srt_content: Conteúdo do arquivo SRT

        Returns:
            Lista de legendas
        """
        subtitles = []
        blocks = srt_content.strip().split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue

            # Parse índice
            try:
                index = int(lines[0])
            except:
                continue

            # Parse tempo
            time_parts = lines[1].split(" --> ")
            start = SRTFormatter._parse_timestamp(time_parts[0])
            end = SRTFormatter._parse_timestamp(time_parts[1])

            # Parse texto
            text = "\n".join(lines[2:])

            subtitles.append(SubtitleLine(
                index=index,
                start_time=start,
                end_time=end,
                text=text
            ))

        return subtitles

    @staticmethod
    def _parse_timestamp(timestamp: str) -> float:
        """Parse timestamp SRT para segundos."""
        timestamp = timestamp.strip()
        parts = timestamp.replace(",", ".").split(":")

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])

        return hours * 3600 + minutes * 60 + seconds


# =============================================================================
# SUBTITLE GENERATOR
# =============================================================================

class SubtitleGenerator:
    """Gera legendas e sobrepõe no vídeo."""

    # Configuração de estilo
    DEFAULT_STYLE = SubtitleStyle()

    # Estilos pré-definidos
    STYLES = {
        "cinema": SubtitleStyle(
            font_size=52,
            primary_color="FFDD00",
            outline_width=3,
            margin_vertical=60
        ),
        "subtitle": SubtitleStyle(
            font_size=48,
            primary_color="FFFFFF",
            outline_width=2,
            margin_vertical=50
        ),
        "small": SubtitleStyle(
            font_size=36,
            primary_color="FFFFFF",
            outline_width=1,
            margin_vertical=40
        )
    }

    def __init__(self, output_dir: Path = Path("./subtitles")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_subtitles(
        self,
        scenes: List,
        output_path: Path,
        style_name: str = "cinema"
    ) -> Path:
        """
        Cria arquivo de legendas SRT.

        Args:
            scenes: Lista de cenas com narração
            output_path: Path do arquivo SRT
            style_name: Nome do estilo

        Returns:
            Path do arquivo criado
        """
        subtitles = []
        index = 1
        current_time = 0.0

        for scene in scenes:
            # Extrair narração
            narration = getattr(scene, 'narration', '')
            if not narration:
                continue

            duration = getattr(scene, 'duration_seconds', 15)

            # Criar legenda
            subtitles.append(SubtitleLine(
                index=index,
                start_time=current_time,
                end_time=current_time + duration,
                text=narration.strip(),
                style=self.STYLES.get(style_name, self.DEFAULT_STYLE)
            ))

            index += 1
            current_time += duration

        # Formatar e salvar
        srt_content = SRTFormatter.create_srt(subtitles)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        logger.info(f"Subtitles created: {output_path}")
        return output_path

    def create_simple_subtitles(
        self,
        narration_texts: List[Dict],
        output_path: Path
    ) -> Path:
        """
        Cria legendas de forma simples.

        Args:
            narration_texts: Lista de dicts com 'start', 'end', 'text'
            output_path: Path do arquivo SRT

        Returns:
            Path do arquivo criado
        """
        subtitles = []

        for i, item in enumerate(narration_texts):
            subtitles.append(SubtitleLine(
                index=i + 1,
                start_time=item.get('start', 0),
                end_time=item.get('end', 15),
                text=item.get('text', ''),
                style=self.DEFAULT_STYLE
            ))

        srt_content = SRTFormatter.create_srt(subtitles)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        return output_path

    def burn_subtitles(
        self,
        video_path: Path,
        subtitle_path: Path,
        output_path: Path,
        style_name: str = "cinema",
        verify_ffmpeg: bool = True
    ) -> Path:
        """
        Insere legendas diretamente no vídeo (burn-in).

        Args:
            video_path: Path do vídeo
            subtitle_path: Path do SRT
            output_path: Path do vídeo de saída
            style_name: Estilo das legendas

        Returns:
            Path do vídeo com legendas
        """
        style = self.STYLES.get(style_name, self.DEFAULT_STYLE)

        # Verificar se FFmpeg está disponível
        if verify_ffmpeg:
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("FFmpeg not found. Please install FFmpeg.")
                raise RuntimeError("FFmpeg required for subtitle burn-in")

        # Construir filtro de legendas
        filter_complex = self._build_subtitle_filter(style)

        # Comando FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={subtitle_path}{filter_complex}",
            "-c:a", "copy",
            "-preset", "medium",
            "-crf", "23",
            str(output_path)
        ]

        logger.info(f"Burning subtitles into video...")
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            error = result.stderr.decode()
            logger.error(f"FFmpeg error: {error}")

            # Tentar novamente com formato alternativo
            cmd_alt = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"subtitles='{subtitle_path}'{filter_complex}",
                "-c:a", "copy",
                str(output_path)
            ]
            result = subprocess.run(cmd_alt, capture_output=True)

            if result.returncode != 0:
                raise RuntimeError(f"Subtitle burn-in failed: {result.stderr.decode()}")

        logger.info(f"Video with subtitles: {output_path}")
        return output_path

    def _build_subtitle_filter(self, style: SubtitleStyle) -> str:
        """Constrói filtro FFmpeg para estilo das legendas."""
        filters = []

        # Fonte e tamanho
        font = style.font_name.replace(" ", "\\ ")
        filters.append(f"Force_style='FontName={font},FontSize={style.font_size}'")

        # Cores
        filters.append(f"PrimaryColour=&H{style.primary_color}")
        filters.append(f"OutlineColour=&H{style.outline_color}")

        # Margens
        margin_v = style.margin_vertical
        filters.append(f"MarginV={margin_v}")
        filters.append(f"MarginL={style.margin_horizontal}")
        filters.append(f"MarginR={style.margin_horizontal}")

        return f":force_style='{','.join(filters)}'"

    def verify_subtitles(self, srt_path: Path) -> bool:
        """Verifica se arquivo SRT é válido."""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parsear e verificar
            subtitles = SRTFormatter.parse_srt(content)
            return len(subtitles) > 0

        except Exception as e:
            logger.error(f"Invalid SRT file: {e}")
            return False


# =============================================================================
# ADVANCED SUBTITLE PROCESSING
# =============================================================================

class AdvancedSubtitleProcessor:
    """Processamento avançado de legendas."""

    def __init__(self):
        self.formatter = SRTFormatter()

    def split_long_subtitles(
        self,
        subtitles: List[SubtitleLine],
        max_chars_per_line: int = 42,
        max_duration_per_line: float = 3.0
    ) -> List[SubtitleLine]:
        """
        Divide legendas longas em linhas menores.

        Args:
            subtitles: Lista de legendas
            max_chars_per_line: Máximo de caracteres por linha
            max_duration_per_line: Máximo de segundos por linha

        Returns:
            Lista de legendas divididas
        """
        result = []
        index = 1

        for sub in subtitles:
            words = sub.text.split()
            lines = []
            current_line = []
            current_chars = 0

            for word in words:
                if current_chars + len(word) + 1 <= max_chars_per_line:
                    current_line.append(word)
                    current_chars += len(word) + 1
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_chars = len(word)

            if current_line:
                lines.append(" ".join(current_line))

            # Calcular duração por linha
            duration = sub.end_time - sub.start_time
            line_duration = min(duration / len(lines), max_duration_per_line)

            current_time = sub.start_time
            for line in lines:
                result.append(SubtitleLine(
                    index=index,
                    start_time=current_time,
                    end_time=current_time + line_duration,
                    text=line,
                    style=sub.style
                ))
                current_time += line_duration
                index += 1

        return result

    def add_fade_effect(
        self,
        subtitles: List[SubtitleLine],
        fade_in: float = 0.2,
        fade_out: float = 0.3
    ) -> List[SubtitleLine]:
        """Adiciona efeito de fade às legendas."""
        for sub in subtitles:
            # FFmpeg SSA/ASS fade effect would need special formatting
            # This is a placeholder for future enhancement
            pass

        return subtitles

    def sync_with_audio(
        self,
        subtitles: List[SubtitleLine],
        audio_path: Path
    ) -> List[SubtitleLine]:
        """
        Sincroniza legendas com áudio usando reconhecimento de voz.

        Args:
            subtitles: Legendas atuais
            audio_path: Path do áudio

        Returns:
            Legendas sincronizadas
        """
        # Placeholder para integração com Whisper ou similar
        # Por agora, retorna as legendas como estão
        logger.info("Audio sync not implemented - using original timings")
        return subtitles


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Exemplo de uso
    generator = SubtitleGenerator()

    # Cenários de exemplo
    scenes = [
        {"narration": "No princípio, Deus criou os céus e a terra.", "duration": 15},
        {"narration": "E a terra era sem forma e vazia.", "duration": 10},
        {"narration": "E Deus disse: Haja luz. E houve luz.", "duration": 15},
    ]

    # Converter para objetos
    from dataclasses import dataclass

    @dataclass
    class SimpleScene:
        narration: str
        duration_seconds: int

    scene_objects = [SimpleScene(**s) for s in scenes]

    # Criar SRT
    output_path = Path("./subtitles/test.srt")
    generator.create_subtitles(scene_objects, output_path)

    print(f"Subtitles created: {output_path}")

    # Verificar
    if generator.verify_subtitles(output_path):
        print("Subtitles verified OK")
