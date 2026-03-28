# Script-to-Cinema: Sistema de Automação de Vídeos Bíblicos

Sistema automatizado para criar vídeos bíblicos cinematográficos de alta qualidade (4:30 min) usando **LTX2** no ComfyUI.

---

## 🎬 Estrutura do Vídeo

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESTRUTURA DO VÍDEO (4:30)                    │
├─────────────┬─────────────┬─────────────────┬─────────────┤
│  00:00-00:30  │  00:30-00:45  │   00:45-04:15   │  04:15-04:30  │
├─────────────┼─────────────┼─────────────────┼─────────────┤
│   TRAILER   │   ABERTURA  │ HISTÓRIA PRINCIPAL│  FECHAMENTO │
│ Hollywoodiano│   do Canal  │  (LTX2 Render)   │   do Canal  │
│             │   (Fixed)    │    ~14 cenas      │   (Fixed)   │
└─────────────┴─────────────┴─────────────────┴─────────────┘
```

---

## 🔄 Fluxo de Trabalho

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE COMPLETO                              │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────┐│
│  │  GEMINI  │  │   LTX2   │  │  FFmpeg  │  │ Subtitles │  │YT  ││
│  │  Script  │→ │ Renderer │→ │  Assemb. │→ │   Burn    │→ │Up  ││
│  │          │  │ (GPU)    │  │          │  │  (FFmpeg) │  │    ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────┘│
│       ↓            ↓             ↓             ↓             ↓     │
│   Supabase      Kaggle        Local         Local        YouTube  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Arquivos do Sistema

```
D:\automatico videos\
├── cinema_generator.py        # ⭐ Orquestrador principal
├── ltx2_workflow.py         # ⭐ Workflow LTX2 migrado
├── youtube_uploader.py       # ⭐ Upload API YouTube
├── subtitle_generator.py      # ⭐ Legendas FFmpeg
│
├── video_queue_schema.sql    # ⭐ Schema Supabase
├── video_weekly.yml         # ⭐ GitHub Actions
│
├── WORKFLOW - SVI PRO.json  # (Original - reference)
│
└── .github\workflows\
    └── video_weekly.yml     # Workflow principal
```

---

## 🚀 Instalação

### 1. Dependências Python

```bash
pip install google-generativeai supabase python-dotenv Pillow
pip install google-api-python-client google-auth
```

### 2. Instalar FFmpeg

```bash
# Windows (chocolatey)
choco install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 3. Variáveis de Ambiente (.env)

```env
# ===========================================
# GOOGLE GEMINI
# ===========================================
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# ===========================================
# SUPABASE
# ===========================================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# ===========================================
# YOUTUBE API
# ===========================================
YOUTUBE_SERVICE_ACCOUNT={"type":"service_account",...}

# ===========================================
# KAGGLE (para GPU)
# ===========================================
KAGGLE_USERNAME=your-kaggle-username
KAGGLE_KEY=your-kaggle-key
KAGGLE_NOTEBOOK_ID=username/notebook/notebook-id

# ===========================================
# COMFYUI
# ===========================================
COMFYUI_URL=http://127.0.0.1:8181
```

---

## 🎯 Uso

### Linha de Comando

```bash
# Gerar vídeo para tema específico
python cinema_generator.py --theme "A Criação"

# Processar próximo da fila
python cinema_generator.py

# Listar status da fila
python cinema_generator.py --list-queue

# Pular upload YouTube
python cinema_generator.py --skip-youtube
```

### API Python

```python
from cinema_generator import generate_video_with_ltx2

video = generate_video_with_ltx2(
    theme="A Crucifixão de Jesus",
    gemini_api_key="YOUR_KEY",
    supabase_url="URL",
    supabase_key="KEY"
)

print(f"Video: {video.final_video_path}")
print(f"YouTube: {video.youtube_url}")
```

---

## 🎨 Workflow LTX2 (Migrado do Wan-SVI)

### Modelo Principal

```python
# LTX2 - Lightricks Video Model
model = "LTX-Video-2B-v0.9.safetensors"

# Vantagens vs Wan-SVI:
# ✅ Geração nativa de áudio + vídeo
# ✅ Sincronização automática perfeita
# ✅ Qualidade profissional 16:9
# ✅ Sem marcas d'água
# ✅ Controles finos de câmera
```

### Parâmetros

```python
{
    "width": 1280,      # 16:9
    "height": 720,
    "fps": 24,
    "steps": 40,
    "cfg": 3.5,
    "duration": 15     # segundos
}
```

---

## 📝 Legendas Automáticas

### Estilo Cinematográfico

```
┌────────────────────────────────────────┐
│                                        │
│     E Deus disse: Haja luz.            │  ← Amarelo (#FFDD00)
│     E houve luz.                        │    Contorno preto
│                                        │
└────────────────────────────────────────┘
              ↓
       FFmpeg Burn-in
```

### Geração

```python
from subtitle_generator import SubtitleGenerator

generator = SubtitleGenerator()

# Criar SRT
generator.create_subtitles(scenes, "legendas.srt")

# Queimar no vídeo
generator.burn_subtitles(
    video_path="video.mp4",
    subtitle_path="legendas.srt",
    output_path="video_com_legendas.mp4"
)
```

---

## 🗄️ Schema Supabase

### Tabela: video_queue

```sql
CREATE TABLE public.video_queue (
    id BIGSERIAL PRIMARY KEY,
    theme TEXT NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabela: biblical_videos

```sql
CREATE TABLE public.biblical_videos (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    theme TEXT,
    youtube_id TEXT,
    video_url TEXT,
    status TEXT DEFAULT 'pending',
    duration_seconds INTEGER DEFAULT 270,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🔧 GitHub Actions Secrets

| Secret | Descrição |
|--------|-----------|
| `GEMINI_API_KEY` | Google Gemini API |
| `SUPABASE_URL` | URL do projeto |
| `SUPABASE_ANON_KEY` | Chave pública |
| `SUPABASE_SERVICE_KEY` | Chave de serviço |
| `YOUTUBE_SERVICE_ACCOUNT` | JSON service account |
| `KAGGLE_USERNAME` | Username Kaggle |
| `KAGGLE_KEY` | API Key Kaggle |
| `COMFYUI_URL` | URL do ComfyUI |

---

## 📅 Schedule

| Dia | Horário | Ação |
|-----|---------|------|
| **Sábado** | 09:00 AM (BRT) | Pipeline automático |

---

## 🌐 Integração com Site

```html
<script>
  const { createClient } = supabase;
  const client = createClient(SUPABASE_URL, ANON_KEY);

  async function loadVideos() {
    const { data } = await client
      .from('biblical_videos')
      .select('title, video_url, thumbnail_url, created_at')
      .eq('status', 'published')
      .order('created_at', { ascending: false });

    data.forEach(video => {
      document.write(`
        <div class="video-card">
          <a href="${video.video_url}">
            <img src="${video.thumbnail_url}">
            <h3>${video.title}</h3>
          </a>
        </div>
      `);
    });
  }

  loadVideos();
</script>
```

---

## ✅ Checklist de Configuração

- [ ] Configurar Supabase (executar SQL)
- [ ] Criar bucket de storage
- [ ] Configurar YouTube API (service account)
- [ ] Adicionar temas na fila
- [ ] Configurar GitHub Secrets
- [ ] Testar pipeline manualmente

---

**Versão**: 1.0.0 (Script-to-Cinema com LTX2)
