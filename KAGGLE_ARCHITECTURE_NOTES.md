# 🧠 Notas de Arquitetura: Pipeline de Cinema Bíblico (LTX2 + Kaggle + GitHub)

**Data da Última Atualização:** 28 de Março de 2026
**Status Atual:** 🟢 Funcional e Integrado (Aguardando Teste End-to-End via GitHub)

## 🏗️ O que construímos até agora:

### 1. Motor Autônomo Kaggle (Renderizador)
- **Arquivo:** `ltx2_workflow.py`
- **O que faz:** Ao invés de dependermos de acessar o Kaggle manualmente e ligar o servidor ComfyUI, criamos uma Classe (`KaggleLTX2Renderer`) que gera dinamicamente um arquivo Python gigantesco (`render_notebook.py`).
- **Magia:** Esse script gerado ensina o servidor da nuvem (GPU T4x2 ou P100) a instalar o ComfyUI do zero, baixar os 10.3GB do LTX-Video, iniciar o servidor silenciosamente e renderizar TODAS as cenas (1 a 16) sequencialmente sem intervenção humana, fechando o servidor no final e salvando os MP4 na pasta `/kaggle/working/output/`.
- **Bugs Resolvidos:** Corrigimos o terrível erro de sintaxe do `KeyError` e formatação do `JSON`, substituindo o `.format()` por um template `.replace()` usando aspas simples dentro do dicionário (`build_ltx2_workflow`).

### 2. Maestro do GitHub Actions (Orquestrador)
- **Arquivo:** `.github/workflows/video_weekly.yml`
- **O que faz:** O Github agora é o Cérebro Central. No Sábado, ele acorda, usa a API do Gemini 1.5/2.0 para gerar os Roteiros (Prompts) e usa a API Oficial do Kaggle (`kaggle kernels push`) para injetar nosso script lá dentro.
- **Polling Loop:** Ele fica esperando em loop (de 60 em 60s) usando `kaggle kernels status` até o Kaggle terminar o vídeo (leva cerca de 45m). Quando o status vira "completed", ele roda `kaggle kernels output` para baixar os MP4 crus de volta para a máquina do Github.
- **Bugs Resolvidos:** Removemos a dependência de Keys inválidas e forçamos o Github a logar e esperar no lugar do usuário.

### 3. Integrações de Chaves (Variáveis de Ambiente)
- **Kaggle API:** Descobrimos que a API do Kaggle rejeita os tokens novos (`KGAT_...`). É obrigatório usar a chave **Legacy API Key** (32 caracteres alfanuméricos) para o bot funcionar via CLI. 
- A chave correta (`f1713eb...`) foi validada localmente! (Salva nas instruções do Desktop).

---

## 🎯 PRÓXIMOS PASSOS (O que falta/Como melhorar):

1. **Apertar o Botão Final:** O usuário precisa colocar a chave Legacy no **GitHub Secrets** (`KAGGLE_KEY`) e clicar em "Run Workflow" no repositório `script-to-cinema` para aprovar o teste de ponta a ponta (Mangá -> Kaggle -> FFmpeg -> YouTube).
2. **Audio/Voz:** O sistema atual usa FFmpeg via Github Actions (`cinema_generator.py`) para juntar os vídeos brutos do Kaggle em um só. Caso precise melhorar a voz (se o Edge-TTS falhar ou ficar robótico), será a próxima área de ataque local.
3. **Erros Temporários no Kaggle:** Se eventualmente o Kaggle recusar iniciar a máquina por "Cota Excedida", precisaremos implementar um script de Retry (Tentativa) no Github Actions para tentar novamente após algumas horas.
4. **Miniaturas (Thumbnails):** A classe de "Thumbnail" pode ser ativada na sequência para gerar a Capa do YouTube pegando o "Frame 1" do Trailer.

---
*Este arquivo existe para a IA (e para você) lembrar do fluxo lógico exato caso façam modificações em semanas/meses futuros!*
