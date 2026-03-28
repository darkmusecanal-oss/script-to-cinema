-- ============================================================
-- Script-to-Cinema: Tabela video_queue
-- ============================================================
-- Execute este SQL no Supabase SQL Editor para criar a fila
-- de vídeos bíblicos para processamento automático.
-- ============================================================

-- ============================================================
-- 1. CRIAR TABELA video_queue
-- ============================================================

CREATE TABLE IF NOT EXISTS public.video_queue (
    id BIGSERIAL PRIMARY KEY,
    
    -- Tema bíblico
    theme TEXT NOT NULL,
    title TEXT,
    
    -- URL de origem
    source_url TEXT,
    video_id TEXT,
    
    -- Status do processamento
    status TEXT DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'rendering', 'completed', 'failed')
    ),
    
    -- Prioridade (maior = processa primeiro)
    priority INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Dados extras
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- 2. CRIAR TABELA biblical_videos
-- ============================================================

CREATE TABLE IF NOT EXISTS public.biblical_videos (
    id BIGSERIAL PRIMARY KEY,
    
    -- Identificação
    title TEXT NOT NULL,
    theme TEXT,
    source_url TEXT,
    
    -- URLs
    video_url TEXT,
    youtube_id TEXT,
    thumbnail_url TEXT,
    local_path TEXT,
    
    -- Status
    status TEXT DEFAULT 'pending',
    
    -- Metadados
    duration_seconds INTEGER DEFAULT 270,
    scene_count INTEGER DEFAULT 0,
    
    -- SEO
    description TEXT,
    tags TEXT[],
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Extras
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- FK para queue
    queue_id INTEGER REFERENCES public.video_queue(id)
);

-- ============================================================
-- 3. ÍNDICES
-- ============================================================

-- video_queue
CREATE INDEX IF NOT EXISTS idx_video_queue_status 
    ON public.video_queue(status);

CREATE INDEX IF NOT EXISTS idx_video_queue_priority 
    ON public.video_queue(priority DESC, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_video_queue_created 
    ON public.video_queue(created_at DESC);

-- biblical_videos
CREATE INDEX IF NOT EXISTS idx_biblical_videos_youtube 
    ON public.biblical_videos(youtube_id);

CREATE INDEX IF NOT EXISTS idx_biblical_videos_status 
    ON public.biblical_videos(status);

CREATE INDEX IF NOT EXISTS idx_biblical_videos_created 
    ON public.biblical_videos(created_at DESC);

-- ============================================================
-- 4. TRIGGER updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_video_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_video_queue_updated_at ON public.video_queue;
CREATE TRIGGER update_video_queue_updated_at
    BEFORE UPDATE ON public.video_queue
    FOR EACH ROW
    EXECUTE FUNCTION public.update_video_queue_updated_at();

DROP TRIGGER IF EXISTS update_biblical_videos_updated_at ON public.biblical_videos;
CREATE TRIGGER update_biblical_videos_updated_at
    BEFORE UPDATE ON public.biblical_videos
    FOR EACH ROW
    EXECUTE FUNCTION public.update_biblical_videos_updated_at();


-- ============================================================
-- 5. ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.video_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biblical_videos ENABLE ROW LEVEL SECURITY;

-- Video Queue
CREATE POLICY "Public read video_queue" ON public.video_queue
    FOR SELECT USING (true);

CREATE POLICY "Service insert video_queue" ON public.video_queue
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Service update video_queue" ON public.video_queue
    FOR UPDATE USING (true);

-- Biblical Videos
CREATE POLICY "Public read videos" ON public.biblical_videos
    FOR SELECT USING (true);

CREATE POLICY "Service insert videos" ON public.biblical_videos
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Service update videos" ON public.biblical_videos
    FOR UPDATE USING (true);


-- ============================================================
-- 6. EXEMPLOS DE TEMAS
-- ============================================================

/*
INSERT INTO public.video_queue (theme, title, priority) VALUES
('A Criação - Gênesis 1', 'No Princípio - A Criação', 10),
('Adão e Eva', 'O Jardim do Éden', 9),
('Davi e Golias', 'Goliattes - O Gigante', 8),
('A Arca de Noé', 'O Dilúvio', 9),
('Moisés e as Tábuas', 'As Tábuas da Lei', 8),
('Jesus Crucificado', 'Gólgota - A Cruz', 10),
('A Ressurreição', 'Ressurreição - O Filho', 10),
('O Dilúvio', 'Noé e a Arca', 8),
('Abraão e Isaac', 'O Sacrifício de Abraão', 9),
('Apocalipse', 'O Fim dos Tempos', 10);
*/


-- ============================================================
-- 7. FUNÇÕES ÚTEIS
-- ============================================================

-- Próximo item pendente
CREATE OR REPLACE FUNCTION get_next_video_queue_item()
RETURNS SETOF public.video_queue AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM public.video_queue
    WHERE status = 'pending'
    ORDER BY priority DESC, created_at ASC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- Status da fila
CREATE OR REPLACE FUNCTION get_video_queue_stats()
RETURNS TABLE(status TEXT, count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(vq.status, 'total') as status,
        COUNT(*)::bigint as count
    FROM public.video_queue vq
    GROUP BY ROLLUP(vq.status)
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Registrar vídeo completo
CREATE OR REPLACE FUNCTION register_completed_video(
    p_title TEXT,
    p_theme TEXT,
    p_youtube_id TEXT,
    p_youtube_url TEXT,
    p_duration INTEGER,
    p_queue_id INTEGER
)
RETURNS BIGINT AS $$
DECLARE
    new_id BIGINT;
BEGIN
    INSERT INTO public.biblical_videos (
        title, theme, youtube_id, video_url, 
        status, duration_seconds, queue_id
    ) VALUES (
        p_title, p_theme, p_youtube_id, p_youtube_url,
        'published', p_duration, p_queue_id
    )
    RETURNING id INTO new_id;

    -- Atualizar queue
    UPDATE public.video_queue
    SET status = 'completed',
        metadata = jsonb_set(metadata, '{completed_at}', to_jsonb(NOW()))
    WHERE id = p_queue_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;
