"""
Script-to-Cinema Modules
========================
Sistema de automação de vídeos bíblicos com LTX2.
"""

from .cinema_generator import (
    CinemaGenerator,
    generate_video_with_ltx2,
    GeminiVideoScriptGenerator,
    VideoQueueManager,
    VideoStructure,
    VideoScene,
    GeneratedVideo
)

from .ltx2_workflow import (
    LTX2WorkflowGenerator,
    LTX2Params,
    VideoScene as LTXVideoScene,
    CinematicPromptEnhancer,
    KaggleLTX2Renderer
)

from .youtube_uploader import (
    YouTubeUploader,
    ThumbnailGenerator,
    VideoMetadata,
    UploadResult
)

from .subtitle_generator import (
    SubtitleGenerator,
    SubtitleStyle,
    SubtitleLine,
    SRTFormatter,
    AdvancedSubtitleProcessor
)

__all__ = [
    # Cinema Generator
    'CinemaGenerator',
    'generate_video_with_ltx2',
    'GeminiVideoScriptGenerator',
    'VideoQueueManager',
    'VideoStructure',
    'VideoScene',
    'GeneratedVideo',
    
    # LTX2 Workflow
    'LTX2WorkflowGenerator',
    'LTX2Params',
    'CinematicPromptEnhancer',
    'KaggleLTX2Renderer',
    
    # YouTube
    'YouTubeUploader',
    'ThumbnailGenerator',
    'VideoMetadata',
    'UploadResult',
    
    # Subtitles
    'SubtitleGenerator',
    'SubtitleStyle',
    'SubtitleLine',
    'SRTFormatter',
    'AdvancedSubtitleProcessor'
]
