# ============================================================
# Script-to-Cinema: SDXL + SVD Image-to-Video Pipeline
# Roda no Kaggle com GPU gratuita T4 (16GB VRAM)
# ============================================================
# Fase 1: SDXL gera imagens cinematográficas 16:9
# Fase 2: SVD XT 1.1 anima cada imagem
# Fase 3: FFmpeg monta o vídeo final
# ============================================================

import os
import sys
import time
import json
import glob
import shutil
import requests
import subprocess
from pathlib import Path

OUTPUT_DIR = Path("/kaggle/working/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
COMFYUI_URL = "http://127.0.0.1:8188"

# ============================================================
# DADOS DAS CENAS (gerados pelo Gemini)
# ============================================================

SCENES_DATA = [
  {
    "title": "Trailer",
    "prompt": "Cinematic wide shot of Adam kneeling on scorched earth outside the massive, glowing golden gates of Eden, his back to the camera, head bowed in agonizing silence, dramatic HBO-style lighting, swirling dust and embers, hyper-realistic textures, 8K, epic scale.",
    "duration": 30
  },
  {
    "title": "Opening",
    "prompt": "A warm, reverent cinematic shot of an ancient scholar's study with golden light, an open vellum manuscript on a wooden table, dust motes dancing in the sunbeams.",
    "duration": 15
  },
  {
    "title": "O Choque da Realidade",
    "prompt": "Extreme close-up of Adam's eyes reflecting the fading glow of Eden’s gates, pupils dilated, expression of profound ontological shock, cinematic lighting, 8K.",
    "duration": 15
  },
  {
    "title": "O Primeiro Toque da Dor",
    "prompt": "Close-up of Adam's hand touching a sharp thorn on a wild bush, a single drop of blood forming, bokeh background of a desolate landscape, hyper-realistic.",
    "duration": 15
  },
  {
    "title": "A Geometria do Caos",
    "prompt": "Wide shot of Adam standing on a rocky cliff overlooking a vast, untamed wilderness at twilight, wind whipping his hair, cinematic atmosphere, cold blue tones.",
    "duration": 15
  },
  {
    "title": "O Peso do Suor",
    "prompt": "Medium shot of Adam wiping sweat from his forehead with a dirty hand, muscles strained, looking down at a primitive stone tool, golden hour lighting, cinematic grit.",
    "duration": 15
  },
  {
    "title": "A Ausência da Voz",
    "prompt": "Adam sitting alone by a small fire at night, looking up at the vast Milky Way, expression of deep longing and cosmic loneliness, cinematic shadows.",
    "duration": 15
  },
  {
    "title": "Memória como Tortura",
    "prompt": "A dreamlike, blurry vision of the lush Garden of Eden seen through a veil of mist, ethereal lighting, vibrant colors contrasting with Adam’s dark foreground.",
    "duration": 15
  },
  {
    "title": "O Luto da Perfeição",
    "prompt": "Adam and Eve sitting back-to-back in a cave entrance, shrouded in shadow, looking in opposite directions, symbolizing the first interpersonal tension and collective grief.",
    "duration": 15
  },
  {
    "title": "A Descoberta do Tempo",
    "prompt": "Close-up of an hourglass made of stone and sand on the ground, or Adam watching leaves wither and turn to dust in his palm, 8K photorealistic.",
    "duration": 15
  },
  {
    "title": "O Nome das Coisas Mortas",
    "prompt": "Adam looking at the skeleton of a fallen animal in the desert, his face displaying a mix of curiosity and horror, cinematic backlight, 8K.",
    "duration": 15
  },
  {
    "title": "A Psicologia do Medo",
    "prompt": "Adam looking at his reflection in a dark, murky pond, his face distorted by ripples, representing the fragmented human psyche after the fall.",
    "duration": 15
  },
  {
    "title": "O Grito Interno",
    "prompt": "Adam standing on a mountain peak under a stormy sky, chest expanded, mouth closed, but his neck veins straining, powerful cinematic composition.",
    "duration": 15
  },
  {
    "title": "A Primeira Oração",
    "prompt": "Adam pressing his forehead against a cold stone altar, a single tear falling, soft divine light breaking through clouds in the distance, cinematic hope.",
    "duration": 15
  },
  {
    "title": "O Legado do Exílio",
    "prompt": "Side profile of Adam walking toward a distant horizon, his silhouette small against the vast sky, a sense of resilience and tragic nobility, 8K.",
    "duration": 15
  },
  {
    "title": "Closing",
    "prompt": "An ancient leather-bound scroll being slowly rolled up on a dark wooden desk, soft divine light from a window illuminating the texture of the paper.",
    "duration": 15
  }
]

# ============================================================
# FASE 0: INSTALAÇÃO AUTOMÁTICA
# ============================================================

def install_all():
    print("=" * 60)
    print("🚀 FASE 0: Instalando ComfyUI + SDXL + SVD")
    print("=" * 60)

    # 1. Clonar ComfyUI
    if not os.path.exists("/tmp/ComfyUI"):
        print("📦 Clonando ComfyUI...")
        os.system("git clone https://github.com/comfyanonymous/ComfyUI.git /tmp/ComfyUI")

    # 2. Corrigir PyTorch (Kaggle P100/T4 compatibilidade) e instalar dependencias
    print("📦 Instalando PyTorch 2.4.1 (Suporte P100/T4) e dependencias...")
    os.system("pip install -q torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121")
    os.system("pip install -q -r /tmp/ComfyUI/requirements.txt")
    os.system("pip install -q imageio-ffmpeg requests huggingface_hub")

    # 3. Baixar SDXL Base 1.0 (fp16 = ~6.5GB)
    ckpt_dir = "/tmp/ComfyUI/models/checkpoints"
    os.makedirs(ckpt_dir, exist_ok=True)

    sdxl_path = f"{ckpt_dir}/sd_xl_base_1.0.safetensors"
    min_sdxl_size = 5_000_000_000  # 5GB minimo
    if not os.path.exists(sdxl_path) or os.path.getsize(sdxl_path) < min_sdxl_size:
        if os.path.exists(sdxl_path):
            os.remove(sdxl_path)
        print("📥 Baixando SDXL Base 1.0 (~6.5GB) via huggingface_hub...")
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="stabilityai/stable-diffusion-xl-base-1.0",
            filename="sd_xl_base_1.0.safetensors",
            local_dir=ckpt_dir,
            local_dir_use_symlinks=False
        )
        print(f"   SDXL: {os.path.getsize(sdxl_path) / 1e9:.1f} GB")

    # 4. Baixar SVD XT 1.1 (~4.1GB) - PRECISA de download cuidadoso
    svd_path = f"{ckpt_dir}/svd_xt_1_1.safetensors"
    min_svd_size = 3_000_000_000  # 3GB minimo
    if not os.path.exists(svd_path) or os.path.getsize(svd_path) < min_svd_size:
        if os.path.exists(svd_path):
            os.remove(svd_path)
        print("📥 Baixando SVD XT 1.1 (~4.1GB) via huggingface_hub...")
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="stabilityai/stable-video-diffusion-img2vid-xt-1-1",
            filename="svd_xt_1_1.safetensors",
            local_dir=ckpt_dir,
            local_dir_use_symlinks=False
        )
        actual_size = os.path.getsize(svd_path) if os.path.exists(svd_path) else 0
        print(f"   SVD: {actual_size / 1e9:.1f} GB")
        if actual_size < min_svd_size:
            print("❌ ERRO: SVD download corrompido! Tentando via wget direto...")
            os.system(f"rm -f {svd_path}")
            os.system(f"wget -c 'https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1/resolve/main/svd_xt_1_1.safetensors?download=true' -O {svd_path}")

    # Verificacao final
    for name, path, min_s in [("SDXL", sdxl_path, min_sdxl_size), ("SVD", svd_path, min_svd_size)]:
        if os.path.exists(path):
            sz = os.path.getsize(path)
            status = "OK" if sz > min_s else "CORROMPIDO"
            print(f"   {name}: {sz / 1e9:.2f} GB [{status}]")
        else:
            print(f"   {name}: ARQUIVO NAO ENCONTRADO!")

    # 5. Instalar VideoHelperSuite
    custom_dir = "/tmp/ComfyUI/custom_nodes"
    if not os.path.exists(f"{custom_dir}/ComfyUI-VideoHelperSuite"):
        print("📦 Instalando VideoHelperSuite...")
        os.system(f"git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git {custom_dir}/ComfyUI-VideoHelperSuite")
        os.system(f"pip install -q -r {custom_dir}/ComfyUI-VideoHelperSuite/requirements.txt")

    # 6. Instalar Frame Interpolation (RIFE)
    if not os.path.exists(f"{custom_dir}/ComfyUI-Frame-Interpolation"):
        print("📦 Instalando Frame Interpolation (RIFE)...")
        os.system(f"git clone https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git {custom_dir}/ComfyUI-Frame-Interpolation")
        os.system(f"pip install -q -r {custom_dir}/ComfyUI-Frame-Interpolation/requirements.txt")

    print("✅ Instalacao completa!")


# ============================================================
# COMFYUI SERVER
# ============================================================

def start_comfyui():
    print("\n🚀 Ligando ComfyUI Server...")
    log_file = open("/kaggle/working/comfy.log", "w")
    process = subprocess.Popen(
        ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"],
        cwd="/tmp/ComfyUI", stdout=log_file, stderr=subprocess.STDOUT
    )

    for attempt in range(180):
        try:
            r = requests.get(COMFYUI_URL, timeout=2)
            if r.status_code == 200:
                print("✅ ComfyUI Online!")
                return process
        except:
            time.sleep(2)

    print("❌ ComfyUI não iniciou. Log:")
    os.system("tail -50 /kaggle/working/comfy.log")
    raise Exception("ComfyUI falhou ao iniciar")


# ============================================================
# COMFYUI CLIENT
# ============================================================

class ComfyClient:
    def __init__(self):
        self.url = COMFYUI_URL
        self.client_id = f"kaggle_{int(time.time())}"

    def queue(self, workflow):
        payload = {"prompt": workflow, "client_id": self.client_id}
        try:
            r = requests.post(f"{self.url}/prompt", json=payload, timeout=30)
            if r.status_code == 200:
                return r.json().get("prompt_id")
            print(f"❌ Erro {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"❌ Conexão: {e}")
        return None

    def wait(self, prompt_id, timeout=600):
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(f"{self.url}/history/{prompt_id}", timeout=10)
                if r.status_code == 200:
                    h = r.json()
                    if prompt_id in h:
                        entry = h[prompt_id]
                        status = entry.get("status", {})
                        status_str = status.get("status_str", "")
                        completed = status.get("completed", False)
                        # Check for success
                        if status_str == "success" or completed:
                            return True
                        # Check for error
                        if status_str == "error" or "error" in str(status).lower():
                            msgs = entry.get("status", {}).get("messages", [])
                            print(f"❌ Workflow falhou: {status_str}")
                            for msg in msgs[-3:]:
                                print(f"   Detalhe: {str(msg)[:200]}")
                            return False
            except:
                pass
            time.sleep(5)
        print("⏰ Timeout!")
        return False


# ============================================================
# FASE 1: GERAR IMAGENS COM SDXL
# ============================================================

def build_sdxl_workflow(prompt, negative="", seed=42, prefix="scene"):
    neg = negative or "low quality, blurry, distorted, watermark, text, logo, cartoon, anime, cgi, ugly, deformed"
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 576, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": 25, "cfg": 7.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "denoise": 1.0
        }},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}}
    }


def generate_all_images(client):
    print("\n" + "=" * 60)
    print("🎨 FASE 1: Gerando imagens com SDXL")
    print("=" * 60)

    os.makedirs("/tmp/ComfyUI/input", exist_ok=True)

    for i, scene in enumerate(SCENES_DATA):
        prefix = f"scene_{i:02d}"
        print(f"\n🖼️  Imagem {i+1}/{len(SCENES_DATA)}: {scene.get('title', 'Cena')}")

        prompt = scene["prompt"]
        # Adicionar enhancement cinematográfico
        prompt += ". cinematic 4K, film grain, dramatic lighting, biblical atmosphere, masterpiece, best quality, 16:9"

        seed = int(time.time()) + i
        workflow = build_sdxl_workflow(prompt, seed=seed, prefix=prefix)
        pid = client.queue(workflow)

        if pid:
            print(f"   Prompt {pid[:12]}... enviado. Aguardando...")
            if client.wait(pid, timeout=120):
                # Copiar imagem gerada para pasta input do ComfyUI
                output_dir = "/tmp/ComfyUI/output"
                imgs = sorted(glob.glob(f"{output_dir}/{prefix}*.png"))
                if imgs:
                    dst = f"/tmp/ComfyUI/input/{prefix}.png"
                    shutil.copy2(imgs[-1], dst)
                    print(f"   ✅ Imagem salva: {prefix}.png")
                else:
                    print(f"   ⚠️  Imagem não encontrada no output!")
            else:
                print(f"   ❌ Falha na geração da imagem!")
        else:
            print(f"   ❌ Falha ao enviar workflow!")

    print("\n✅ Todas as imagens geradas!")


# ============================================================
# FASE 2: ANIMAR IMAGENS COM SVD XT 1.1
# ============================================================

def build_svd_workflow(image_name, motion_bucket=127, seed=42, prefix="video"):
    return {
        "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {
            "ckpt_name": "svd_xt_1_1.safetensors"
        }},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "SVD_img2vid_Conditioning", "inputs": {
            "width": 1024, "height": 576,
            "video_frames": 25,
            "motion_bucket_id": motion_bucket,
            "fps": 8,
            "augmentation_level": 0.0,
            "clip_vision": ["1", 1],
            "init_image": ["2", 0],
            "vae": ["1", 2]
        }},
        "4": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": 20, "cfg": 2.5,
            "sampler_name": "euler", "scheduler": "karras",
            "positive": ["3", 0], "negative": ["3", 1],
            "latent_image": ["3", 2], "denoise": 1.0
        }},
        "5": {"class_type": "VAEDecode", "inputs": {
            "samples": ["4", 0], "vae": ["1", 2]
        }},
        "6": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["5", 0],
            "frame_rate": 8,
            "loop_count": 0,
            "filename_prefix": prefix,
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True
        }}
    }


MOTION_BUCKETS = {
    "Trailer": 180,
    "Opening": 80,
    "Closing": 70,
}


def animate_all_images(client):
    print("\n" + "=" * 60)
    print("🎬 FASE 2: Animando imagens com SVD XT 1.1")
    print("=" * 60)

    for i, scene in enumerate(SCENES_DATA):
        image_name = f"scene_{i:02d}.png"
        video_prefix = f"video_{i:02d}"
        title = scene.get("title", "Cena")

        # Verificar se a imagem existe
        img_path = f"/tmp/ComfyUI/input/{image_name}"
        if not os.path.exists(img_path):
            print(f"\n⚠️  Pulando cena {i+1} (imagem não encontrada)")
            continue

        # Motion bucket baseado no tipo de cena
        motion = MOTION_BUCKETS.get(title, 120)

        print(f"\n🎥 Vídeo {i+1}/{len(SCENES_DATA)}: {title} (motion={motion})")

        seed = int(time.time()) + i + 100
        workflow = build_svd_workflow(image_name, motion_bucket=motion, seed=seed, prefix=video_prefix)
        pid = client.queue(workflow)

        if pid:
            print(f"   Prompt {pid[:12]}... enviado. Aguardando (~2-3 min)...")
            if client.wait(pid, timeout=600):
                print(f"   ✅ Vídeo {video_prefix} renderizado!")
            else:
                print(f"   ❌ Falha na animação!")
        else:
            print(f"   ❌ Falha ao enviar workflow SVD!")

    print("\n✅ Todas as animações concluídas!")


# ============================================================
# FASE 3: MONTAR VÍDEO FINAL COM FFMPEG
# ============================================================

def assemble_final_video():
    print("\n" + "=" * 60)
    print("🎞️  FASE 3: Montando vídeo final com FFmpeg")
    print("=" * 60)

    output_dir = "/tmp/ComfyUI/output"
    final_dir = "/kaggle/working/output"
    os.makedirs(final_dir, exist_ok=True)

    # Encontrar todos os vídeos gerados
    videos = sorted(glob.glob(f"{output_dir}/video_*.mp4"))
    print(f"Encontrados {len(videos)} clipes de vídeo")

    if not videos:
        print("❌ Nenhum vídeo encontrado!")
        return

    processed = []
    for i, vid in enumerate(videos):
        scene = SCENES_DATA[i] if i < len(SCENES_DATA) else {}
        target_duration = scene.get("duration", 15)

        # Processar cada clipe: esticar para duração alvo com slow-motion cinematográfico
        out_path = f"{final_dir}/processed_{i:02d}.mp4"

        # Obter duração original
        probe_cmd = f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{vid}"'
        result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
        try:
            original_duration = float(result.stdout.strip())
        except:
            original_duration = 3.0

        # Calcular fator de slow-motion
        speed_factor = original_duration / target_duration
        if speed_factor < 0.1:
            speed_factor = 0.25  # Mínimo 0.25x

        print(f"  Clipe {i+1}: {original_duration:.1f}s → {target_duration}s (speed={speed_factor:.2f}x)")

        # FFmpeg: slow-motion + upscale para 1280x720
        cmd = (
            f'ffmpeg -y -i "{vid}" '
            f'-vf "setpts={1/speed_factor}*PTS,scale=1280:720:flags=lanczos" '
            f'-r 24 -c:v libx264 -preset medium -crf 20 '
            f'-t {target_duration} -an '
            f'"{out_path}"'
        )
        os.system(cmd)
        if os.path.exists(out_path):
            processed.append(out_path)

    if not processed:
        print("❌ Nenhum clipe processado!")
        return

    # Criar lista de concatenação
    concat_file = f"{final_dir}/concat.txt"
    with open(concat_file, "w") as f:
        for p in processed:
            f.write(f"file '{p}'\n")

    # Concatenar tudo
    final_path = f"{final_dir}/cinema_final.mp4"
    cmd = (
        f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" '
        f'-c:v libx264 -preset medium -crf 20 -c:a aac '
        f'"{final_path}"'
    )
    os.system(cmd)

    if os.path.exists(final_path):
        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        print(f"\n🎬 VÍDEO FINAL: {final_path} ({size_mb:.1f} MB)")
    else:
        print("❌ Falha na concatenação final!")

    # Copiar imagens originais e vídeos individuais para output
    for img in glob.glob(f"/tmp/ComfyUI/output/scene_*.png"):
        shutil.copy2(img, final_dir)
    for vid in glob.glob(f"/tmp/ComfyUI/output/video_*.mp4"):
        shutil.copy2(vid, final_dir)

    print("✅ Todos os arquivos copiados para /kaggle/working/output/")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🎬 SCRIPT-TO-CINEMA: SDXL + SVD PIPELINE")
    print(f"📊 Total de cenas: {len(SCENES_DATA)}")
    print("=" * 60)

    install_all()
    process = start_comfyui()

    try:
        client = ComfyClient()
        generate_all_images(client)
        animate_all_images(client)
        assemble_final_video()

        print("\n" + "=" * 60)
        print("🏆 PIPELINE COMPLETO!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if process:
            process.terminate()
        print("🔌 Servidor desligado.")
