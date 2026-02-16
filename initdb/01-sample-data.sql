-- ============================================
-- Sample Database Schema & Data for Hasura Test
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Users table
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(150),
    avatar_url TEXT,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'editor', 'user')),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Categories table
-- ============================================
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Articles table
-- ============================================
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    content TEXT,
    excerpt TEXT,
    cover_image_url TEXT,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    view_count INTEGER DEFAULT 0,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Tags table
-- ============================================
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL
);

-- Article-Tag many-to-many
CREATE TABLE article_tags (
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- ============================================
-- Comments table
-- ============================================
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    is_approved BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- Orders table (e-commerce sample)
-- ============================================
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    stock_quantity INTEGER DEFAULT 0,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_amount NUMERIC(12,2) DEFAULT 0,
    shipping_address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE NOT NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL,
    total_price NUMERIC(12,2) NOT NULL
);

-- ============================================
-- INSERT SAMPLE DATA
-- ============================================

-- Users
INSERT INTO users (id, username, email, full_name, role) VALUES
    ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'admin', 'admin@example.com', 'Admin User', 'admin'),
    ('b2c3d4e5-f6a7-8901-bcde-f12345678901', 'editor1', 'editor1@example.com', 'Nguyen Van A', 'editor'),
    ('c3d4e5f6-a7b8-9012-cdef-123456789012', 'editor2', 'editor2@example.com', 'Tran Thi B', 'editor'),
    ('d4e5f6a7-b8c9-0123-defa-234567890123', 'user1', 'user1@example.com', 'Le Van C', 'user'),
    ('e5f6a7b8-c9d0-1234-efab-345678901234', 'user2', 'user2@example.com', 'Pham Thi D', 'user'),
    ('f6a7b8c9-d0e1-2345-fabc-456789012345', 'user3', 'user3@example.com', 'Hoang Van E', 'user');

-- Categories
INSERT INTO categories (id, name, slug, description, parent_id) VALUES
    (1, 'Technology', 'technology', 'Articles about technology and software', NULL),
    (2, 'Programming', 'programming', 'Programming tutorials and tips', 1),
    (3, 'DevOps', 'devops', 'DevOps practices and tools', 1),
    (4, 'Lifestyle', 'lifestyle', 'Lifestyle and personal growth', NULL),
    (5, 'Travel', 'travel', 'Travel destinations and guides', 4),
    (6, 'Food', 'food', 'Food reviews and recipes', 4),
    (7, 'AI & Machine Learning', 'ai-ml', 'Artificial Intelligence and ML', 1),
    (8, 'Web Development', 'web-dev', 'Frontend and backend web development', 2);
SELECT setval('categories_id_seq', 8);

-- Tags
INSERT INTO tags (id, name, slug) VALUES
    (1, 'Python', 'python'),
    (2, 'JavaScript', 'javascript'),
    (3, 'Docker', 'docker'),
    (4, 'GraphQL', 'graphql'),
    (5, 'PostgreSQL', 'postgresql'),
    (6, 'React', 'react'),
    (7, 'Hasura', 'hasura'),
    (8, 'Tutorial', 'tutorial'),
    (9, 'Beginner', 'beginner'),
    (10, 'Advanced', 'advanced');
SELECT setval('tags_id_seq', 10);

-- Articles
INSERT INTO articles (id, title, slug, content, excerpt, author_id, category_id, status, view_count, published_at) VALUES
    (1, 'Getting Started with GraphQL and Hasura', 'getting-started-graphql-hasura',
     'GraphQL is a query language for APIs that gives clients the power to ask for exactly what they need. Hasura provides instant GraphQL APIs over PostgreSQL...',
     'Learn how to build powerful GraphQL APIs with Hasura.',
     'b2c3d4e5-f6a7-8901-bcde-f12345678901', 2, 'published', 1250, NOW() - INTERVAL '10 days'),

    (2, 'Docker Compose for Development Environments', 'docker-compose-development',
     'Docker Compose simplifies multi-container Docker applications. In this guide, we will set up a complete development environment...',
     'Set up your dev environment with Docker Compose.',
     'b2c3d4e5-f6a7-8901-bcde-f12345678901', 3, 'published', 890, NOW() - INTERVAL '7 days'),

    (3, 'Building REST APIs with Python Flask', 'building-rest-apis-python-flask',
     'Flask is a lightweight WSGI web application framework in Python. It is designed to make getting started quick and easy...',
     'A comprehensive guide to Flask REST APIs.',
     'c3d4e5f6-a7b8-9012-cdef-123456789012', 2, 'published', 2100, NOW() - INTERVAL '15 days'),

    (4, 'Introduction to PostgreSQL Window Functions', 'postgresql-window-functions',
     'Window functions perform calculations across a set of table rows that are somehow related to the current row...',
     'Master PostgreSQL window functions with examples.',
     'c3d4e5f6-a7b8-9012-cdef-123456789012', 2, 'published', 650, NOW() - INTERVAL '3 days'),

    (5, 'React Hooks Deep Dive', 'react-hooks-deep-dive',
     'React Hooks let you use state and other React features without writing a class. In this deep dive, we explore useState, useEffect, useContext...',
     'Everything you need to know about React Hooks.',
     'b2c3d4e5-f6a7-8901-bcde-f12345678901', 8, 'published', 3200, NOW() - INTERVAL '20 days'),

    (6, 'AI-Powered Code Review Tools', 'ai-powered-code-review',
     'Artificial intelligence is transforming software development. Code review tools powered by AI can catch bugs, suggest improvements...',
     'Explore AI tools that enhance code reviews.',
     'c3d4e5f6-a7b8-9012-cdef-123456789012', 7, 'draft', 0, NULL),

    (7, 'Top 10 Street Food in Hanoi', 'top-10-street-food-hanoi',
     'Hanoi is famous for its vibrant street food culture. From pho to bun cha, here are the top 10 must-try dishes...',
     'Discover the best street food in Hanoi.',
     'd4e5f6a7-b8c9-0123-defa-234567890123', 6, 'published', 5400, NOW() - INTERVAL '30 days'),

    (8, 'Backpacking Through Southeast Asia', 'backpacking-southeast-asia',
     'Southeast Asia offers incredible experiences for budget travelers. From Thailand to Vietnam, discover the best routes...',
     'Your ultimate guide to backpacking in Southeast Asia.',
     'e5f6a7b8-c9d0-1234-efab-345678901234', 5, 'published', 1800, NOW() - INTERVAL '12 days');
SELECT setval('articles_id_seq', 8);

-- Article Tags
INSERT INTO article_tags (article_id, tag_id) VALUES
    (1, 4), (1, 7), (1, 8),              -- GraphQL, Hasura, Tutorial
    (2, 3), (2, 8), (2, 9),              -- Docker, Tutorial, Beginner
    (3, 1), (3, 8), (3, 9),              -- Python, Tutorial, Beginner
    (4, 5), (4, 10),                      -- PostgreSQL, Advanced
    (5, 2), (5, 6), (5, 10),             -- JavaScript, React, Advanced
    (6, 1), (6, 10),                      -- Python, Advanced
    (7, 8),                               -- Tutorial
    (8, 8);                               -- Tutorial

-- Comments
INSERT INTO comments (id, article_id, user_id, parent_id, body, is_approved) VALUES
    (1, 1, 'd4e5f6a7-b8c9-0123-defa-234567890123', NULL, 'Great article! Hasura makes GraphQL so easy to use.', true),
    (2, 1, 'e5f6a7b8-c9d0-1234-efab-345678901234', NULL, 'Can you do a follow-up on subscriptions?', true),
    (3, 1, 'b2c3d4e5-f6a7-8901-bcde-f12345678901', 2, 'Sure! I am planning a subscriptions tutorial next week.', true),
    (4, 3, 'f6a7b8c9-d0e1-2345-fabc-456789012345', NULL, 'Very helpful for beginners. Thanks!', true),
    (5, 5, 'd4e5f6a7-b8c9-0123-defa-234567890123', NULL, 'The useEffect examples are exactly what I needed.', true),
    (6, 7, 'e5f6a7b8-c9d0-1234-efab-345678901234', NULL, 'I love bun cha! Best food in Hanoi!', true),
    (7, 7, 'f6a7b8c9-d0e1-2345-fabc-456789012345', 6, 'You should try bun dau mam tom too!', true),
    (8, 2, 'd4e5f6a7-b8c9-0123-defa-234567890123', NULL, 'Docker is a game changer for development.', false);
SELECT setval('comments_id_seq', 8);

-- Products
INSERT INTO products (id, name, sku, description, price, stock_quantity, category_id, user_id) VALUES
    (1, 'Python Programming Book', 'BOOK-PY-001', 'Complete guide to Python programming', 29.99, 150, 2, 'b2c3d4e5-f6a7-8901-bcde-f12345678901'),
    (2, 'JavaScript Masterclass', 'BOOK-JS-001', 'Advanced JavaScript techniques', 34.99, 80, 2, 'b2c3d4e5-f6a7-8901-bcde-f12345678901'),
    (3, 'Docker for Developers', 'BOOK-DK-001', 'Docker and containerization guide', 39.99, 60, 3, 'c3d4e5f6-a7b8-9012-cdef-123456789012'),
    (4, 'GraphQL in Action', 'BOOK-GQ-001', 'Build modern APIs with GraphQL', 44.99, 45, 2, 'c3d4e5f6-a7b8-9012-cdef-123456789012'),
    (5, 'Mechanical Keyboard', 'HW-KB-001', 'Cherry MX Brown switches, RGB', 129.99, 25, 1, 'd4e5f6a7-b8c9-0123-defa-234567890123'),
    (6, 'Developer Sticker Pack', 'ACC-ST-001', 'Pack of 50 programming stickers', 9.99, 500, 1, 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
    (7, 'USB-C Hub', 'HW-HB-001', '7-in-1 USB-C hub with HDMI', 49.99, 100, 1, 'e5f6a7b8-c9d0-1234-efab-345678901234'),
    (8, 'Noise Cancelling Headphones', 'HW-HP-001', 'Wireless ANC headphones', 199.99, 30, 1, 'f6a7b8c9-d0e1-2345-fabc-456789012345');
SELECT setval('products_id_seq', 8);

-- Orders
INSERT INTO orders (id, user_id, status, total_amount, shipping_address, notes) VALUES
    ('11111111-1111-1111-1111-111111111111', 'd4e5f6a7-b8c9-0123-defa-234567890123', 'delivered', 64.98, '123 Le Loi, District 1, HCMC', 'Please leave at door'),
    ('22222222-2222-2222-2222-222222222222', 'e5f6a7b8-c9d0-1234-efab-345678901234', 'shipped', 179.98, '456 Tran Hung Dao, Hoan Kiem, Hanoi', NULL),
    ('33333333-3333-3333-3333-333333333333', 'f6a7b8c9-d0e1-2345-fabc-456789012345', 'confirmed', 259.98, '789 Nguyen Hue, District 1, HCMC', 'Gift wrapping please'),
    ('44444444-4444-4444-4444-444444444444', 'd4e5f6a7-b8c9-0123-defa-234567890123', 'pending', 9.99, '123 Le Loi, District 1, HCMC', NULL),
    ('55555555-5555-5555-5555-555555555555', 'e5f6a7b8-c9d0-1234-efab-345678901234', 'cancelled', 44.99, '456 Tran Hung Dao, Hoan Kiem, Hanoi', 'Changed my mind');

-- Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price) VALUES
    ('11111111-1111-1111-1111-111111111111', 1, 1, 29.99, 29.99),
    ('11111111-1111-1111-1111-111111111111', 2, 1, 34.99, 34.99),
    ('22222222-2222-2222-2222-222222222222', 5, 1, 129.99, 129.99),
    ('22222222-2222-2222-2222-222222222222', 7, 1, 49.99, 49.99),
    ('33333333-3333-3333-3333-333333333333', 8, 1, 199.99, 199.99),
    ('33333333-3333-3333-3333-333333333333', 3, 1, 39.99, 39.99),
    ('33333333-3333-3333-3333-333333333333', 6, 2, 9.99, 19.98),
    ('44444444-4444-4444-4444-444444444444', 6, 1, 9.99, 9.99),
    ('55555555-5555-5555-5555-555555555555', 4, 1, 44.99, 44.99);

-- ============================================
-- Create updated_at trigger function
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_articles_updated_at BEFORE UPDATE ON articles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
