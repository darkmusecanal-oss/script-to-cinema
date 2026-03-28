"""
LTX2 Workflow Generator
=======================
Workflow migrado do Wan-SVI para LTX2 (Lightricks Video Model).
Inclui geração nativa de áudio + vídeo sincronizado.

Vantagens do LTX2:
- Geração nativa de áudio + vídeo
- Sincronização automática perfeita
- Qualidade profissional 16:9
- Sem marcas d'água
- Controles finos de câmera
"""

import json
import time
import requests
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VideoScene:
    """Cena de vídeo individual."""
    scene_number: int
    title: str
    prompt: str
    narration: str = ""
    duration_seconds: int = 15
    scene_type: str = "cinematic"
    seed: Optional[int] = None


@dataclass
class LTX2Params:
    """Parâmetros do modelo LTX2."""
    # Modelo principal
    model_name: str = "LTX-Video-2B-v0.9.safetensors"

    # Dimensões (múltiplos de 16)
    width: int = 1280
    height: int = 720  # 16:9

    # Duração (fps * segundos)
    fps: int = 24
    duration_seconds: int = 15

    # Qualidade
    steps: int = 40
    cfg: float = 3.5
    gpu_memory_boost: bool = True

    # Câmera
    camera_mode: str = "cinematic"  # static, linear, cinematic
    camera_preset: str = "medium_steady"

    # Áudio
    generate_audio: bool = True
    audio_prompt: str = ""

    # LoRA (opcional)
    lora_path: Optional[str] = None
    lora_strength: float = 1.0


# =============================================================================
# LTX2 WORKFLOW TEMPLATE
# =============================================================================

LTX2_WORKFLOW_TEMPLATE = {}


# =============================================================================
# NEGATIVE PROMPTS
# =============================================================================

LTX2_NEGATIVE_PROMPT = """low quality, blurry, distorted, watermark, text, logo,
animation, cartoon, anime, cgi, fake, artificial, overexposed, underexposed,
noise, grain, flicker, stutter, choppy, jarring, sudden cuts"""


# =============================================================================
# CINEMATIC PROMPT ENHANCER
# =============================================================================

class CinematicPromptEnhancer:
    """Melhora prompts para estilo cinematográfico bíblico."""

    ENHANCEMENTS = {
        "cinematic": {
            "lighting": "cinematic lighting, volumetric light, golden hour, god rays",
            "camera": "tracking shot, dramatic camera movement, shallow depth of field",
            "atmosphere": "epic scale, dramatic atmosphere, epic composition"
        },
        "trailer": {
            "lighting": "dramatic lighting, high contrast, epic lighting",
            "camera": "dynamic camera movement, sweeping shot, aerial view",
            "atmosphere": "high impact, epic scale, cinematic drama, suspenseful"
        },
        "story": {
            "lighting": "natural lighting, chiaroscuro, warm tones",
            "camera": "steady shot, medium close-up, emotional framing",
            "atmosphere": "intimate, emotional, storytelling, reverent"
        },
        "closing": {
            "lighting": "soft lighting, warm glow, peaceful",
            "camera": "slow zoom out, wide shot",
            "atmosphere": "reflective, peaceful, closing mood"
        }
    }

    BIBLICAL_ELEMENTS = [
        "biblical setting", "ancient architecture", "sacred atmosphere",
        "divine presence", "heavenly light", "sacred geometry"
    ]

    def enhance(self, prompt: str, scene_type: str = "cinematic") -> str:
        """Melhora prompt com elementos cinematográficos."""
        enhancements = self.ENHANCEMENTS.get(scene_type, self.ENHANCEMENTS["cinematic"])

        enhanced = prompt.strip()

        # Adicionar elementos cinematográficos
        if enhancements["lighting"]:
            enhanced += f". {enhancements['lighting']}"
        if enhancements["camera"]:
            enhanced += f". {enhancements['camera']}"
        if enhancements["atmosphere"]:
            enhanced += f". {enhancements['atmosphere']}"

        # Adicionar elementos bíblicos aleatórios
        import random
        biblical = random.sample(self.BIBLICAL_ELEMENTS, min(2, len(self.BIBLICAL_ELEMENTS)))
        enhanced += f". {', '.join(biblical)}"

        # Estilo técnico
        enhanced += ". cinematic 4K, film grain, anamorphic lens flare, 16:9 aspect ratio"

        return enhanced


# =============================================================================
# LTX2 WORKFLOW GENERATOR
# =============================================================================

class LTX2WorkflowGenerator:
    """Gerador de workflow LTX2 para ComfyUI."""

    def __init__(self, comfyui_url: str = "http://127.0.0.1:8181"):
        self.comfyui_url = comfyui_url
        self.client_id = f"cinema_{int(time.time())}"
        self.prompt_enhancer = CinematicPromptEnhancer()

    def build_workflow(
        self,
        prompt: str,
        negative_prompt: str = LTX2_NEGATIVE_PROMPT,
        duration_seconds: int = 15,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        steps: int = 40,
        cfg: float = 3.5,
        seed: Optional[int] = None,
        scene_type: str = "cinematic",
        audio_prompt: str = "",
        generate_audio: bool = True,
        filename_prefix: str = "scene"
    ) -> Dict:
        """
        Constrói workflow completo para LTX2.

        Args:
            prompt: Prompt positivo
            negative_prompt: Prompt negativo
            duration_seconds: Duração em segundos
            width: Largura do vídeo
            height: Altura do vídeo
            fps: Frames por segundo
            steps: Passos de amostragem
            cfg: Classifier-free guidance
            seed: Seed (None = aleatório)
            scene_type: Tipo de cena
            audio_prompt: Prompt para áudio
            generate_audio: Gerar áudio
            filename_prefix: Prefixo do arquivo

        Returns:
            Workflow dict pronto para o ComfyUI
        """
        import random
        seed = seed or random.randint(0, 2**32 - 1)

        # Calcular frames
        frames = duration_seconds * fps

        # Garantir dimensões múltiplas de 16
        width = (width // 16) * 16
        height = (height // 16) * 16

        # Melhorar prompt
        enhanced_prompt = self.prompt_enhancer.enhance(prompt, scene_type)

        # Construir workflow
        workflow = {
            "3": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "LTX-Video-2B-v0.9.safetensors"}
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": enhanced_prompt, "clip": ["3", 1]}
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["3", 1]}
            },
            "6": {
                "class_type": "EmptyLatentVideo",
                "inputs": {
                    "width": width,
                    "height": height,
                    "frames": frames,
                    "batch_size": 1
                }
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["6", 0]
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["3", 2]}
            },
            "10": {
                "class_type": "VideoCombine",
                "inputs": {
                    "fps": fps,
                    "hdr_comparison_max": 128,
                    "loop_count": 0,
                    "ping_pong_frame": False,
                    "save_output": True,
                    "images": ["8", 0]
                }
            },
            "15": {
                "class_type": "SaveVideo",
                "inputs": {
                    "filename_prefix": filename_prefix,
                    "video": ["10", 0],
                    "format": "mp4",
                    "quality": 95
                }
            }
        }

        # Adicionar áudio se solicitado
        if generate_audio and audio_prompt:
            workflow["13"] = {
                "class_type": "AudioGenerate",
                "inputs": {
                    "audio_prompt": audio_prompt,
                    "duration": duration_seconds,
                    "seed": seed
                }
            }
            workflow["14"] = {
                "class_type": "VideoAudioMerge",
                "inputs": {
                    "video": ["15", 0],
                    "audio": ["13", 0],
                    "volume": 0.8,
                    "fade_out_duration": 1.0
                }
            }
            # Redirecionar saída para o merge
            workflow["15"]["inputs"]["video"] = ["14", 0]

        return workflow

    def render_scene(
        self,
        prompt: str,
        output_path: Path,
        duration_seconds: int = 15,
        scene_type: str = "cinematic",
        audio_prompt: str = "",
        **kwargs
    ) -> bool:
        """
        Renderiza uma cena via ComfyUI API.

        Args:
            prompt: Prompt da cena
            output_path: Path de saída do vídeo
            duration_seconds: Duração
            scene_type: Tipo de cena
            audio_prompt: Prompt para áudio

        Returns:
            True se bem sucedido
        """
        logger.info(f"Rendering scene: {prompt[:50]}...")

        # Construir workflow
        workflow = self.build_workflow(
            prompt=prompt,
            duration_seconds=duration_seconds,
            scene_type=scene_type,
            audio_prompt=audio_prompt,
            filename_prefix=output_path.stem,
            **kwargs
        )

        # Enviar para ComfyUI
        prompt_id = self._queue_prompt(workflow)
        if not prompt_id:
            logger.error("Failed to queue prompt")
            return False

        # Aguardar conclusão
        success = self._wait_for_completion(prompt_id, timeout=duration_seconds * 10)

        if success:
            logger.info(f"Scene rendered: {output_path}")

        return success

    def render_batch(
        self,
        scenes: List[VideoScene],
        output_dir: Path
    ) -> List[Path]:
        """
        Renderiza múltiplas cenas em lote.

        Args:
            scenes: Lista de VideoScene
            output_dir: Diretório de saída

        Returns:
            Lista de paths dos vídeos gerados
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for scene in scenes:
            output_path = output_dir / f"scene_{scene.scene_number:02d}.mp4"

            success = self.render_scene(
                prompt=scene.prompt,
                output_path=output_path,
                duration_seconds=scene.duration_seconds,
                scene_type=scene.scene_type,
                audio_prompt=scene.narration,
                filename_prefix=f"scene_{scene.scene_number:02d}"
            )

            if success:
                paths.append(output_path)

        return paths

    def _queue_prompt(self, workflow: Dict) -> Optional[str]:
        """Envia prompt para fila do ComfyUI."""
        url = f"{self.comfyui_url}/prompt"
        payload = {"prompt": workflow, "client_id": self.client_id}

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("prompt_id")
        except Exception as e:
            logger.error(f"Failed to queue prompt: {e}")

        return None

    def _wait_for_completion(self, prompt_id: str, timeout: int = 300) -> bool:
        """Aguarda execução do prompt."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Verificar histórico
                url = f"{self.comfyui_url}/history/{prompt_id}"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        status = history[prompt_id].get("status", {})
                        if status.get("state") == "completed":
                            return True
                        elif status.get("state") == "failed":
                            return False

                time.sleep(5)

            except Exception as e:
                logger.warning(f"Status check error: {e}")

        return False


# =============================================================================
# KAGGLE INTEGRATION
# =============================================================================

class KaggleLTX2Renderer:
    """Renderer LTX2 via Kaggle Notebook."""

    NOTEBOOK_CODE_TEMPLATE = '''# Script-to-Cinema: LTX2 Video Renderer Auto-Installer
# Executa no Kaggle com GPU gratuita (T4 x2)

import os
import sys
import time
import json
import base64
import requests
import subprocess
from pathlib import Path

# ============================================================
# PARÂMETROS E CONFIGS
# ============================================================

OUTPUT_DIR = Path("/kaggle/working/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
COMFYUI_URL = "{comfyui_url}"

SCENES_DATA = {scenes_json}

# ============================================================
# INSTALADOR AUTOMÁTICO DO COMFYUI E LTX-VIDEO
# ============================================================
def install_requirements():
    print("🚀 [Fase 1] Inicializando instalador automático do ComfyUI em /tmp...")
    
    # 1. Clonar ComfyUI no diretório temporário
    if not os.path.exists("/tmp/ComfyUI"):
        print("Clonando repositório ComfyUI...")
        os.system("git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/ComfyUI")
    
    # 2. Instalar dependências básicas
    print("Instalando dependências via pip...")
    os.system("pip install -r /tmp/ComfyUI/requirements.txt")
    os.system("pip install imageio-ffmpeg requests")
    
    # 3. Baixar Modelo LTX Video (Checkpoint)
    ckpt_dir = "/tmp/ComfyUI/models/checkpoints"
    os.makedirs(ckpt_dir, exist_ok=True)
    ltx_model_path = f"{ckpt_dir}/LTX-Video-2B-v0.9.safetensors"
    if not os.path.exists(ltx_model_path):
        print(f"Baixando LTX-Video (Isso pode demorar)...")
        os.system(f"wget -c https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.safetensors -O {ltx_model_path}")
    
    # 4. Baixar encoder T5XXL
    clip_dir = "/tmp/ComfyUI/models/clip"
    os.makedirs(clip_dir, exist_ok=True)
    t5_path = f"{clip_dir}/t5xxl_fp8_e4m3fn.safetensors"
    if not os.path.exists(t5_path):
        print("Baixando T5 XXL Text Encoder...")
        os.system(f"wget -c https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors -O {t5_path}")
        
    # 5. Instalar ComfyUI-VideoHelperSuite (necessário para VideoCombine)
    custom_nodes_dir = "/tmp/ComfyUI/custom_nodes"
    if not os.path.exists(f"{custom_nodes_dir}/ComfyUI-VideoHelperSuite"):
        print("Instalando VideoHelperSuite...")
        os.system(f"git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git {custom_nodes_dir}/ComfyUI-VideoHelperSuite")
        os.system(f"pip install -r {custom_nodes_dir}/ComfyUI-VideoHelperSuite/requirements.txt")

    # 6. Instalar ComfyUI-LTXVideo (necessário para EmptyLatentVideo)
    if not os.path.exists(f"{custom_nodes_dir}/ComfyUI-LTXVideo"):
        print("Instalando ComfyUI-LTXVideo...")
        os.system(f"git clone https://github.com/kijai/ComfyUI-LTXVideo.git {custom_nodes_dir}/ComfyUI-LTXVideo")
        os.system(f"pip install -r {custom_nodes_dir}/ComfyUI-LTXVideo/requirements.txt")

# ============================================================
# COMFYUI CLIENT E RUNNER
# ============================================================

def start_comfyui():
    print("🚀 [Fase 2] Ligando o Servidor ComfyUI...")
    log_file = open("comfy.log", "w")
    process = subprocess.Popen(["python", "main.py"], cwd="/tmp/ComfyUI", stdout=log_file, stderr=subprocess.STDOUT)
    
    print("Aguardando ComfyUI carregar os modelos e abrir a porta 8188 (pode levar alguns minutos)...")
    for _ in range(150):
        try:
            r = requests.get(COMFYUI_URL, timeout=2)
            if r.status_code == 200:
                print("✅ ComfyUI Local Online!")
                return process
        except requests.exceptions.ConnectionError:
            time.sleep(2)
            
    print("❌ Falha ao iniciar ComfyUI após 5 minutos. Log do ComfyUI:")
    os.system("cat comfy.log")
    raise Exception("Servidor ComfyUI não iniciou.")

class ComfyUIClient:
    def __init__(self, address="127.0.0.1", port=8188):
        self.address = address
        self.port = port
        self.base_url = f"http://{self.address}:{self.port}"
        self.client_id = f"kaggle_{int(time.time())}"

    def queue_prompt(self, workflow):
        url = f"{self.base_url}/prompt"
        payload = {"prompt": workflow, "client_id": self.client_id}
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code != 200:
                print(f"❌ Erro ComfyUI ({response.status_code}): {response.text}")
                return None
            return response.json().get("prompt_id")
        except Exception as e:
            print(f"❌ Falha de Conexão no Prompt: {str(e)}")
            return None

    def get_history(self, prompt_id):
        url = f"{self.base_url}/history/{prompt_id}"
        return requests.get(url).json()

    def wait_for_completion(self, prompt_id, timeout=900):
        start = time.time()
        while time.time() - start < timeout:
            history = self.get_history(prompt_id)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("state") == "completed":
                    return True
                elif status.get("state") == "failed":
                    return False
            time.sleep(10)
        return False

def build_ltx2_workflow(prompt, duration=15):
    fps = 24
    frames = int(duration * fps)
    return {
        "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "LTX-Video-2B-v0.9.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt + ", cinematic 4K, highest quality", "clip": ["3", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality, watermark, static, blurry", "clip": ["3", 1]}},
        "6": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 768, "height": 512, "length": frames, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["3", 0],
            "seed": int(time.time()),
            "steps": 25,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "denoise": 1.0
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 2]}},
        "10": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0],
            "frame_rate": fps,
            "loop_count": 0,
            "filename_prefix": "LTX2_Scene",
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True
        }}
    }

def render_scenes():
    print(f"🚀 [Fase 3] Iniciando renderização de {len(SCENES_DATA)} cenas...")
    client = ComfyUIClient()
    results = []
    
    for i, scene in enumerate(SCENES_DATA):
        print(f"\\nRenderizando cena {i+1}/{len(SCENES_DATA)}: {scene.get('title', 'Cena')}...")
        workflow = build_ltx2_workflow(prompt=scene["prompt"], duration=scene.get("duration", 15))
        prompt_id = client.queue_prompt(workflow)
        print(f"Prompt {prompt_id} enviado. Aguardando processamento...")
        
        # Timeout de 50 minutos (3000s) para cenas pesadas na P100
        if client.wait_for_completion(prompt_id, timeout=3000):
            print(f"Cena {i+1} concluída com sucesso!")
        else:
            print(f"Erro ao renderizar cena {i+1} (Timeout)!")
            
        results.append({"scene": i+1, "status": "done"})
        
    return results

if __name__ == "__main__":
    print("="*60)
    print("SISTEMA DE AUTOMAÇÃO KAGGLE: SCRIPT TO CINEMA")
    print("="*60)
    
    install_requirements()
    process = start_comfyui()
    
    try:
        results = render_scenes()
        print(f"\\n✅ Renderização finalizada! Total de Cenas: {{len(results)}}")
        
        # Mover arquivos para diretório de saída do Kaggle
        os.system(f"cp -r /tmp/ComfyUI/output/* {OUTPUT_DIR}/")
        print("Arquivos transferidos para /kaggle/working/output/")
    finally:
        print("Desligando servidor...")
        if process:
            process.terminate()
        
    print("Tudo pronto! Fim do script.")
'''

    def __init__(self, comfyui_url: str = "http://127.0.0.1:8188"):
        self.comfyui_url = comfyui_url

    def generate_notebook_code(self, scenes: List[Dict]) -> str:
        """Gera código Python para Kaggle Notebook."""
        code = self.NOTEBOOK_CODE_TEMPLATE.replace("{comfyui_url}", self.comfyui_url)
        code = code.replace("{scenes_json}", json.dumps(scenes, ensure_ascii=False, indent=2))
        return code


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Exemplo de uso
    generator = LTX2WorkflowGenerator()

    scene = VideoScene(
        scene_number=1,
        title="Moisés no Monte Sinai",
        prompt="Moses standing on mountain peak, receiving divine tablets, golden divine light from heaven, dramatic clouds, epic scale, biblical",
        narration="E Deus falou com Moisés no topo da montanha...",
        duration_seconds=15,
        scene_type="cinematic"
    )

    print(f"Enhanced prompt:")
    print(generator.prompt_enhancer.enhance(scene.prompt, scene.scene_type))
