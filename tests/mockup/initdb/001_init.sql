CREATE TABLE IF NOT EXISTS public.customers (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL
);

INSERT INTO public.customers (name) VALUES
('Alice'),
('Bob'),
('Charlie');
