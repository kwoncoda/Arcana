-- MySQL 8 / InnoDB / utf8mb4
-- SET sql_mode = 'STRICT_ALL_TABLES';

-- 1) 사용자
CREATE TABLE users (
  idx           BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '내부 PK(시스템 식별자)',
  id            VARCHAR(255) NOT NULL UNIQUE      COMMENT '로그인용 사용자 ID(사용자 입력값)',
  email         VARCHAR(255) NOT NULL UNIQUE      COMMENT '이메일(로그인/알림/비밀번호 재설정)',
  nickname      VARCHAR(100) NOT NULL UNIQUE      COMMENT '표시 이름(닉네임)',
  password_hash VARCHAR(255) NOT NULL             COMMENT '비밀번호 해시(bcrypt/Argon2 등)',
  type          ENUM('personal','organization') NOT NULL COMMENT '사용자 종류(personal/organization)',
  active        TINYINT(1) NOT NULL DEFAULT 1     COMMENT '계정 활성 여부(1=활성, 0=비활성/차단)',
  created       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '계정 생성 시각',
  last_login    DATETIME NULL                     COMMENT '마지막 로그인 시각'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='사용자 계정';

-- 2) 조직
CREATE TABLE organizations (
  idx     BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '조직 PK',
  name    VARCHAR(200) NOT NULL UNIQUE      COMMENT '조직명',
  created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '조직 생성 시각'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='조직(회사/팀)';

-- 3) 조직 권한(초대/승인 없음; 바로 가입)
CREATE TABLE memberships (
  idx               BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '멤버십 PK',
  user_idx          BIGINT NOT NULL                   COMMENT '사용자 FK',
  organization_idx  BIGINT NOT NULL                   COMMENT '조직 FK',
  role              ENUM('owner','admin','member') NOT NULL DEFAULT 'member' COMMENT '조직 내 역할(mvp에서는 member로만 함)',
  created           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '가입(생성) 시각',
  UNIQUE KEY uk_user_org (user_idx, organization_idx),
  KEY idx_org (organization_idx),   -- 조회 최적화
  KEY idx_user (user_idx),          -- 조회 최적화
  CONSTRAINT fk_mem_user FOREIGN KEY (user_idx) REFERENCES users(idx),
  CONSTRAINT fk_mem_org  FOREIGN KEY (organization_idx) REFERENCES organizations(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='조직-사용자 멤버십(역할 포함)';

-- 4) 워크스페이스(개인/조직 공용)
CREATE TABLE workspaces (
  idx               BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '워크스페이스 PK',
  type              ENUM('personal','organization') NOT NULL COMMENT '워크스페이스 종류(personal/organization)',
  name              VARCHAR(200) NOT NULL           COMMENT '워크스페이스 표시 이름',
  owner_user_idx    BIGINT NULL                     COMMENT '개인 워크스페이스 소유자 FK(personal일 때만)',
  organization_idx  BIGINT NULL                     COMMENT '조직 워크스페이스 소속 조직 FK(organization일 때만)',
  created           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시각',
  UNIQUE KEY uk_personal_owner (type, owner_user_idx),     -- 유저당 개인 WS 1개
  UNIQUE KEY uk_org_workspace (type, organization_idx),    -- 조직당 조직 WS 1개
  KEY idx_org (organization_idx),
  CONSTRAINT fk_ws_owner FOREIGN KEY (owner_user_idx) REFERENCES users(idx),
  CONSTRAINT fk_ws_org   FOREIGN KEY (organization_idx) REFERENCES organizations(idx),
  CONSTRAINT chk_ws_shape CHECK (
    (type='personal'     AND owner_user_idx IS NOT NULL AND organization_idx IS NULL) OR
    (type='organization' AND organization_idx IS NOT NULL AND owner_user_idx IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='개인/조직별 논리 공간(색인/소스 귀속 단위)';

-- 5) RAG 인덱스(WS 단위; 조직은 공용 인덱스 1개 권장)
CREATE TABLE rag_indexes (
  idx            BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'RAG 인덱스 메타 PK',
  workspace_idx  BIGINT NOT NULL                   COMMENT '귀속 워크스페이스 FK',
  name           VARCHAR(200) NOT NULL DEFAULT 'default' COMMENT '인덱스 이름',
  index_type     ENUM('faiss','qdrant','weaviate','pgvector','chroma') NOT NULL COMMENT '엔진',
  storage_uri    VARCHAR(1000) NOT NULL           COMMENT 'db 저장 경로',
  dim            INT                               COMMENT '임베딩 차원',
  status         ENUM('ready','building','failed') NOT NULL DEFAULT 'ready' COMMENT '상태',
  object_count   INT NOT NULL DEFAULT 0            COMMENT '외부 오브젝트 수',
  vector_count   INT NOT NULL DEFAULT 0            COMMENT '벡터 엔트리 수',
  updated        DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00' COMMENT '마지막 갱신 시각',
  UNIQUE KEY uk_ws_name (workspace_idx, name),
  KEY idx_ws (workspace_idx),
  CONSTRAINT fk_rag_ws FOREIGN KEY (workspace_idx) REFERENCES workspaces(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='워크스페이스별 RAG 인덱스 메타';

-- 6) 데이터 소스(MVP: Notion, local)
CREATE TABLE data_sources (
  idx            BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '데이터 소스 인스턴스 PK',
  workspace_idx  BIGINT NOT NULL                   COMMENT '소스가 귀속되는 워크스페이스 FK',
  type           ENUM('notion','local','googledrive') NOT NULL COMMENT '소스 종류(MVP: notion, local, googledrive)',
  name           VARCHAR(200) NOT NULL             COMMENT '소스 표시명(구분용)',
  status         ENUM('connected','disconnected','error') NOT NULL DEFAULT 'connected' COMMENT '연결 상태',
  synced         DATETIME NULL                     COMMENT '마지막 성공 동기화 시각',
  created        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시각',
  KEY idx_ws (workspace_idx),
  CONSTRAINT fk_ds_ws FOREIGN KEY (workspace_idx) REFERENCES workspaces(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='외부 데이터 소스 연결(노션, 구글 드라이브 등)';

-- 7) OAuth 자격증명(노션)
CREATE TABLE notion_oauth_credentials (
  idx                   BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '자격증명 PK',
  user_idx              BIGINT NOT NULL                   COMMENT '승인한 사용자 FK(누가 연결했는지)',
  data_source_idx       BIGINT NOT NULL                   COMMENT '연결된 데이터 소스 FK',
  provider              VARCHAR(50) NOT NULL              COMMENT '제공자 식별(예: notion)',
  bot_id                VARCHAR(100) NOT NULL             COMMENT '설치/authorization 고유 ID(Notion 권장)',
  provider_workspace_id VARCHAR(64) NULL                  COMMENT 'Notion 워크스페이스 ID(참고 메타)',
  workspace_name        VARCHAR(255) NULL                 COMMENT '승인 당시 워크스페이스 이름(표시용)',
  workspace_icon        VARCHAR(1000) NULL                COMMENT '승인 당시 워크스페이스 아이콘 URL(표시용)',
  token_type            VARCHAR(20) NOT NULL DEFAULT 'bearer' COMMENT '토큰 타입(일반적으로 bearer)',
  access_token          TEXT NOT NULL                     COMMENT '액세스 토큰(암호화 저장 권장)',
  refresh_token         TEXT NULL                         COMMENT '리프레시 토큰(암호화 저장 권장)',
  expires               DATETIME NULL                     COMMENT '액세스 토큰 만료 시각',
  created               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '자격증명 생성 시각',
  updated               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '자격증명 갱신 시각',
  provider_payload      JSON NULL                         COMMENT '원문 응답 보관(디버그/추적용)',
  UNIQUE KEY uk_provider_bot (provider, bot_id),
  UNIQUE KEY uk_ds_user (data_source_idx, user_idx),
  CONSTRAINT fk_cred_user FOREIGN KEY (user_idx) REFERENCES users(idx),
  CONSTRAINT fk_cred_ds   FOREIGN KEY (data_source_idx) REFERENCES data_sources(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='노션 OAuth 토큰/메타(비밀 값)';

-- 7-1) OAuth 자격증명(구글 드라이브)
CREATE TABLE google_drive_oauth_credentials (
  idx             BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '자격증명 PK',
  user_idx        BIGINT NOT NULL                   COMMENT '승인한 사용자 FK',
  data_source_idx BIGINT NOT NULL                   COMMENT '연결된 데이터 소스 FK',
  provider        VARCHAR(50) NOT NULL DEFAULT 'googledrive' COMMENT '제공자 식별',
  google_user_id  VARCHAR(255) NULL                 COMMENT '구글 사용자 식별자(sub)',
  email           VARCHAR(255) NULL                 COMMENT '구글 계정 이메일',
  token_type      VARCHAR(20) NOT NULL DEFAULT 'Bearer' COMMENT '토큰 타입',
  access_token    TEXT NOT NULL                     COMMENT '액세스 토큰',
  refresh_token   TEXT NULL                         COMMENT '리프레시 토큰',
  scope           TEXT NULL                         COMMENT '동의된 스코프',
  id_token        TEXT NULL                         COMMENT 'ID 토큰(JWT)',
  expires         DATETIME NULL                     COMMENT '액세스 토큰 만료 시각',
  created         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '자격증명 생성 시각',
  updated         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '자격증명 갱신 시각',
  provider_payload JSON NULL                        COMMENT '원본 응답(JSON)',
  UNIQUE KEY uk_google_ds_user (data_source_idx, user_idx),
  KEY idx_google_user (user_idx),
  CONSTRAINT fk_google_cred_user FOREIGN KEY (user_idx) REFERENCES users(idx),
  CONSTRAINT fk_google_cred_ds   FOREIGN KEY (data_source_idx) REFERENCES data_sources(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='구글 드라이브 OAuth 토큰/메타(비밀 값)';

-- 8) 구글 드라이브 Changes API 동기화 상태
CREATE TABLE google_drive_sync_state (
  idx               BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '동기화 상태 PK',
  data_source_idx   BIGINT NOT NULL UNIQUE            COMMENT 'Google Drive 데이터 소스 FK',
  start_page_token  VARCHAR(255) NULL                 COMMENT 'Changes API startPageToken',
  latest_history_id VARCHAR(255) NULL                 COMMENT '마지막 historyId(미사용 가능)',
  bootstrapped_at   DATETIME NULL                     COMMENT '최초 전체 스캔 완료 시각',
  last_synced       DATETIME NULL                     COMMENT '마지막 증분 동기화 시각',
  created           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '레코드 생성 시각',
  updated           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '레코드 갱신 시각',
  CONSTRAINT fk_google_sync_ds FOREIGN KEY (data_source_idx) REFERENCES data_sources(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='구글 드라이브 증분 동기화 상태 저장';

-- 9) 구글 드라이브 파일 스냅샷(변환 기준)
CREATE TABLE google_drive_file_snapshots (
  idx            BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '파일 스냅샷 PK',
  data_source_idx BIGINT NOT NULL                 COMMENT 'Google Drive 데이터 소스 FK',
  file_id        VARCHAR(128) NOT NULL            COMMENT 'Google Drive 파일 ID',
  name           VARCHAR(1024) NULL               COMMENT '파일 이름',
  mime_type      VARCHAR(255) NOT NULL            COMMENT 'MIME 타입',
  md5_checksum   VARCHAR(128) NULL                COMMENT '바이너리 체크섬',
  version        BIGINT NULL                      COMMENT 'Google Workspace 파일 버전',
  modified_time  DATETIME NULL                    COMMENT '마지막 수정 시각',
  web_view_link  VARCHAR(1024) NULL               COMMENT '웹 링크',
  last_synced    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '마지막 인덱싱 시각',
  created        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '레코드 생성 시각',
  updated        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '레코드 갱신 시각',
  UNIQUE KEY uk_google_drive_file (data_source_idx, file_id),
  KEY idx_google_drive_file_ds (data_source_idx),
  CONSTRAINT fk_google_drive_file_ds FOREIGN KEY (data_source_idx) REFERENCES data_sources(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='구글 드라이브 파일 콘텐츠 스냅샷';

-- 10) 노션 동기화 상태(증분/커서만 저장; 컨텐츠는 저장 안 함)
CREATE TABLE notion_data_source_sync_state (
  idx                 BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '동기화 상태 PK',
  data_source_idx     BIGINT NOT NULL UNIQUE            COMMENT '대상 데이터 소스 FK(1:1)',
  last_full_sync      DATETIME NULL                     COMMENT '마지막 전체 스캔 완료 시각',
  since               DATETIME NULL                     COMMENT '증분 기준 시각(예: last_edited_time)',
  next_cursor         VARCHAR(255) NULL                 COMMENT '노션 페이지네이션 재개 커서',
  rate_limited_until  DATETIME NULL                     COMMENT '레이트 리밋 해제 예상 시각',
  created             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '레코드 생성 시각',
  updated             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '마지막 갱신 시각',
  KEY idx_since (since),
  CONSTRAINT fk_sync_ds FOREIGN KEY (data_source_idx) REFERENCES data_sources(idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='노션 동기화 진행 지점(커서/증분만 저장)';
