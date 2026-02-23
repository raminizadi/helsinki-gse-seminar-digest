-- Helsinki GSE Event Calendar — initial schema
-- Run this once on your Supabase project (SQL Editor or psql).

CREATE TABLE IF NOT EXISTS events (
    event_hash   text PRIMARY KEY,
    title        text NOT NULL,
    speaker      text NOT NULL DEFAULT '',
    institution  text NOT NULL DEFAULT '',
    date         date NOT NULL,
    start_time   time,
    end_time     time,
    location     text,
    description  text,
    categories   text[] NOT NULL DEFAULT '{}',
    organizer    text,
    url          text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscribers (
    id            serial PRIMARY KEY,
    email         text UNIQUE NOT NULL,
    status        text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'active', 'unsubscribed')),
    confirm_token text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sent_log (
    id             serial PRIMARY KEY,
    subscriber_id  int NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
    event_hash     text NOT NULL REFERENCES events(event_hash) ON DELETE CASCADE,
    sent_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subscriber_id, event_hash)
);

-- Index for the weekly digest query: "upcoming events not yet sent to subscriber X"
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_sent_log_subscriber ON sent_log(subscriber_id);
