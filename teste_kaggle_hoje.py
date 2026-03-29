import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from supabase import create_client

# Carrega chaves do arquivo .env
load_dotenv("D:/automatico videos/.env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

def generate_test_script():
    print("1. Conectando ao Supabase para buscar o proximo tema...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Busca o ultimo tema pending
    response = client.table("manga_queue").select("*").eq("status", "pending").order("priority", desc=True).limit(1).execute()
    
    if not response.data:
        print("Nenhum tema pendente na manga_queue!")
        return

    theme = response.data[0]["theme"]
    print(f"Tema escolhido: {theme}")

    print("\n2. Chamando Gemini...")
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-flash-latest")

    PROMPT = f"""You are the master dual-agent behind the YouTube channel 'Além do Versículo'.
    You embody two roles:
    1. Agent 3: The Hollywood Trailer Engineer (responsible for the 30s trailer).
    2. Agent 1: The Rational Documentary Scriptwriter (responsible for the main story).

    Your task is to generate a full JSON script for a 4:30 minute biblical cinematic video about: "{theme}".

    === AGENT 3 RULES (THE TRAILER) ===
    - Duration: 30 seconds.
    - Narrative: 4-part structure (Beginning, Middle, Climax, Ending/Branding). Since it's one 'trailer' object, the 'prompt' must describe a fast-paced sequence of these 4 emotional peaks.
    - Prompts: Written in ENGLISH. Describe cinematic lighting, realistic details, high quality, specific character poses and expressions. IMPORTANT: These prompts will be used to generate STILL IMAGES first, then animate them. Describe a single powerful moment, not a sequence.
    - Narration: Written in PORTUGUESE (PT-BR). Max 10-15 words total so it fits 30s with dramatic pauses.
    - Audio/Branding: Mention 'HBO/Netflix style cinematic soundtrack' in the prompt. End with branding 'ALÉM DO VERSÍCULO'.

    === AGENT 1 RULES (THE STORY) ===
    - Approach: Transform the theme into a 'Rational Script'. Do not preach. Focus on the 'WHY' of the facts, uniting faith and reason. Use historical context, psychology, and motivations.
    - Flow (13 story scenes of 15s each):
      - Scenes 1-2 (The Hook): Create immediate mystery or suspense.
      - Scenes 3-10 (Development): Explore the depth of the theme with rational focus and cultural environment evidence.
      - Scenes 11-12 (The Climax): The great revelation or theological plot twist.
      - Scene 13 (Conclusion): Impactful finish and call to reflection.
    - Prompts: Written in ENGLISH. Each prompt describes ONE powerful cinematic moment (a still frame that will be animated). Include specific details: character pose, facial expression, lighting direction, camera angle, environment details. Match the emotional beat of the narration.
    - Narration: Written in PORTUGUESE (PT-BR). EXACTLY 10 to 15 words per scene. Polished, impactful, meant for slow dramatic reading.

    === CRITICAL PROMPT RULES ===
    Each prompt MUST describe a SINGLE MOMENT (like a photograph), not a video sequence.
    Good example: "A weathered Moses standing at the edge of a cliff, his robes billowing in desert wind, eyes closed in deep prayer, golden sunset light illuminating his face from the left, vast wilderness stretching behind him, 8K, cinematic, photorealistic"
    Bad example: "Moses walks across the desert and then climbs the mountain" (this describes motion, not a moment)

    OUTPUT FORMAT (JSON ONLY, PERFECTLY FORMATTED):
    {{
      "title": "Video Title in Portuguese",
      "theme": "{theme}",
      "trailer": {{
        "prompt": "(ENGLISH) A single epic cinematic moment capturing the essence of the theme. 8K, ultra-realistic, cinematic lighting.",
        "narration": "(PT-BR) Trailer voiceover. Max 15 words.",
        "duration": 30
      }},
      "opening_scene": {{
        "prompt": "(ENGLISH) A warm, reverent cinematic shot of an ancient scholar's study with golden light.",
        "narration": "Olá e bem-vindos ao Além do Versículo. Hoje mergulhamos na verdadeira história de {theme}. Fique conosco até o final, pois temos uma surpresa especial para você.",
        "duration": 15
      }},
      "story_scenes": [
        {{
          "scene_number": 1,
          "title": "Scene concept title",
          "prompt": "(ENGLISH) Single cinematic moment. Lighting, pose, expression, environment. 8K photorealistic.",
          "narration": "(PT-BR) 10-15 words focusing on the 'why' and psychology.",
          "duration": 15
        }}
      ],
      "closing_scene": {{
        "prompt": "(ENGLISH) Ancient scroll being rolled up on wooden desk, soft divine light.",
        "narration": "Gostou do episódio? A surpresa prometida é o nosso Mangá Bíblico grátis! Clique no link na descrição para baixar. Inscreva-se e que a paz esteja com você.",
        "duration": 15
      }},
      "description": "YouTube SEO description...",
      "tags": ["tag1", "tag2"]
    }}
    """

    res = model.generate_content(PROMPT)
    text = res.text.replace("```json", "").replace("```", "").strip()
    
    try:
        script = json.loads(text)
    except Exception as e:
        print("Erro ao decodificar JSON gerado pelo Gemini:")
        print(text[:500])
        return

    # Organiza a lista final cronologica de TODAS as cenas
    all_scenes = []
    
    # 1. Trailer
    all_scenes.append({"title": "Trailer", "prompt": script["trailer"]["prompt"], "duration": script["trailer"]["duration"]})
    
    # 2. Abertura
    all_scenes.append({"title": "Opening", "prompt": script["opening_scene"]["prompt"], "duration": script["opening_scene"]["duration"]})
    
    # 3. Historia (13 cenas cronologicas)
    for s in script["story_scenes"]:
        all_scenes.append({"title": s["title"], "prompt": s["prompt"], "duration": s.get("duration", 15)})
        
    # 4. Fechamento
    all_scenes.append({"title": "Closing", "prompt": script["closing_scene"]["prompt"], "duration": script["closing_scene"]["duration"]})

    print(f"\nRoteiro gerado com {len(all_scenes)} cenas narrativas cronologicas!")
    
    # Salvar script legivel local para conferencia
    with open("D:/automatico videos/ultimo_roteiro_gerado.json", "w", encoding="utf-8") as f:
        json.dump(script, f, indent=4, ensure_ascii=False)
    print("Roteiro salvo em: D:/automatico videos/ultimo_roteiro_gerado.json")

    print("\n3. Criando o codigo Python do Kaggle (SDXL + SVD)...")
    import sys
    sys.path.append("D:/automatico videos")
    from ltx2_workflow import KaggleI2VRenderer
    
    renderer = KaggleI2VRenderer("http://127.0.0.1:8188")
    kaggle_code = renderer.generate_notebook_code(all_scenes)
    
    with open("D:/automatico videos/render_notebook_teste.py", "w", encoding="utf-8") as f:
        f.write(kaggle_code)

    print("\n✅ Pronto! Novo pipeline SDXL+SVD gerado em: D:/automatico videos/render_notebook_teste.py")
    print("No Kaggle: colar este código e clicar Run!")

if __name__ == "__main__":
    generate_test_script()
