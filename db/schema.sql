CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_projects (
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects (id),
    PRIMARY KEY (user_id, project_id)
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects (id),
    uploaded_by INTEGER REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX documents_name_active ON documents (name) WHERE deleted_at IS NULL;

CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX conversations_user ON conversations (user_id, updated_at DESC);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX messages_conversation ON messages (conversation_id, id);

CREATE TABLE message_sources (
    message_id INTEGER NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents (id),
    PRIMARY KEY (message_id, document_id)
);

CREATE TABLE message_context_documents (
    message_id INTEGER NOT NULL REFERENCES messages (id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents (id),
    PRIMARY KEY (message_id, document_id)
);

CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    message_id INTEGER UNIQUE REFERENCES messages (id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    is_positive BOOLEAN NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
