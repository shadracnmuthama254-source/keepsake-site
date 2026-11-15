-- Keepsake database schema
-- Works on MySQL 8.0+ and MariaDB 10.4+. Safe to run more than once.
-- Run it with:  python init_db.py

CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  email         VARCHAR(254) NOT NULL,
  display_name  VARCHAR(60)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP    NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS password_resets (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NOT NULL,
  token_hash CHAR(64)     NOT NULL,
  expires_at DATETIME     NOT NULL,
  used_at    DATETIME     NULL DEFAULT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_reset_token (token_hash),
  KEY idx_reset_user (user_id),
  CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collections (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED NOT NULL,
  name        VARCHAR(80)  NOT NULL,
  description VARCHAR(500) NULL,
  color       VARCHAR(16)  NOT NULL DEFAULT 'coral',
  emoji       VARCHAR(32)  NOT NULL DEFAULT '📚',
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_collection_user_name (user_id, name),
  CONSTRAINT fk_collections_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS items (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            INT UNSIGNED NOT NULL,
  collection_id      INT UNSIGNED NULL DEFAULT NULL,
  type               ENUM('memory','photo','note','document','link') NOT NULL,
  title              VARCHAR(200) NOT NULL,
  description        MEDIUMTEXT   NULL,
  url                VARCHAR(2048) NULL,
  item_date          DATE         NOT NULL,
  location           VARCHAR(200) NULL,
  is_favorite        TINYINT(1)   NOT NULL DEFAULT 0,
  file_stored_name   VARCHAR(64)  NULL,
  file_original_name VARCHAR(255) NULL,
  file_mime          VARCHAR(100) NULL,
  file_size          BIGINT UNSIGNED NULL,
  created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_items_user_date (user_id, item_date),
  KEY idx_items_user_type (user_id, type),
  KEY idx_items_user_fav (user_id, is_favorite),
  KEY idx_items_collection (collection_id),
  CONSTRAINT fk_items_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_items_collection FOREIGN KEY (collection_id) REFERENCES collections (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tags (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NOT NULL,
  name       VARCHAR(40)  NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tag_user_name (user_id, name),
  CONSTRAINT fk_tags_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS item_tags (
  item_id INT UNSIGNED NOT NULL,
  tag_id  INT UNSIGNED NOT NULL,
  PRIMARY KEY (item_id, tag_id),
  KEY idx_item_tags_tag (tag_id),
  CONSTRAINT fk_item_tags_item FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
  CONSTRAINT fk_item_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
