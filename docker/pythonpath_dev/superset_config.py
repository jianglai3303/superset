# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# This file is included in the final Docker image and SHOULD be overridden when
# deploying the image to prod. Settings configured here are intended for use in local
# development environments. Also note that superset_config_docker.py is imported
# as a final step as a means to override "defaults" configured here
#
import logging
import os

from celery.schedules import crontab
from flask_caching.backends.filesystemcache import FileSystemCache
from flask_appbuilder import expose
from flask import Blueprint, current_app
from flask import request, jsonify
from datetime import datetime, timedelta


logger = logging.getLogger()

DATABASE_DIALECT = os.getenv("DATABASE_DIALECT")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_PORT = os.getenv("DATABASE_PORT")
DATABASE_DB = os.getenv("DATABASE_DB")

EXAMPLES_USER = os.getenv("EXAMPLES_USER")
EXAMPLES_PASSWORD = os.getenv("EXAMPLES_PASSWORD")
EXAMPLES_HOST = os.getenv("EXAMPLES_HOST")
EXAMPLES_PORT = os.getenv("EXAMPLES_PORT")
EXAMPLES_DB = os.getenv("EXAMPLES_DB")

# The SQLAlchemy connection string.
SQLALCHEMY_DATABASE_URI = (
    f"{DATABASE_DIALECT}://"
    f"{DATABASE_USER}:{DATABASE_PASSWORD}@"
    f"{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)

SQLALCHEMY_EXAMPLES_URI = (
    f"{DATABASE_DIALECT}://"
    f"{EXAMPLES_USER}:{EXAMPLES_PASSWORD}@"
    f"{EXAMPLES_HOST}:{EXAMPLES_PORT}/{EXAMPLES_DB}"
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_CELERY_DB = os.getenv("REDIS_CELERY_DB", "0")
REDIS_RESULTS_DB = os.getenv("REDIS_RESULTS_DB", "1")

RESULTS_BACKEND = FileSystemCache("/app/superset_home/sqllab")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_RESULTS_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG

class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    imports = (
        "superset.sql_lab",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
    )
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    worker_prefetch_multiplier = 1
    task_acks_late = False
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=10, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

FEATURE_FLAGS = {"ALERT_REPORTS": True}
ALERT_REPORTS_NOTIFICATION_DRY_RUN = True
WEBDRIVER_BASEURL = "http://superset:8088/"  # When using docker compose baseurl should be http://superset_app:8088/
# The base URL for the email report hyperlinks.
WEBDRIVER_BASEURL_USER_FRIENDLY = WEBDRIVER_BASEURL
SQLLAB_CTAS_NO_LIMIT = True
# This will make sure the redirect_uri is properly computed, even with SSL offloading
ENABLE_PROXY_FIX = True

from flask_appbuilder.security.manager import AUTH_OAUTH
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "keycloak",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "Superset",
            "client_secret": "Hsq03ihgnbuw26oThwlBP6qzHa7teuTT",
            "api_base_url": "http://host.docker.internal:8080/realms/master/protocol/openid-connect/",
            "client_kwargs": {
                "scope": "email openid profile",
            },
            "request_token_url": None,
            "access_token_url": "http://host.docker.internal:8080/realms/master/protocol/openid-connect/token",
            "userinfo_endpoint": "http://host.docker.internal:8080/realms/master/protocol/openid-connect/userinfo",
            "authorize_url": "http://host.docker.internal:8080/realms/master/protocol/openid-connect/auth",
            "jwks_uri": "http://host.docker.internal:8080/realms/master/protocol/openid-connect/certs",
        },
    }
]

# Map Authlib roles to superset roles
AUTH_ROLE_ADMIN = 'Admin'
AUTH_ROLE_PUBLIC = 'Public'

# Will allow user self registration, allowing to create Flask users from Authorized User
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Admin"
# The default user self registration role
AUTH_ROLES_SYNC_AT_LOGIN = True
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': [
        'http://localhost:3000'
    ]
}
TALISMAN_ENABLED = False
TALISMAN_CONFIG = {
    "content_security_policy": {
        "frame-ancestors": ["*.127.0.0.1:5500", "*.localhost:3000"],
    }
}
HTTP_HEADERS = {
    'X-Frame-Options': 'ALLOWALL'
}
FEATURE_FLAGS = {
    # ... other feature flags
    "EMBEDDED_SUPERSET": True,
}

GUEST_ROLE_NAME = "Admin"

import json
import urllib.request
from jwt.algorithms import RSAAlgorithm
import jwt
from flask import g
from superset.security import SupersetSecurityManager


# Set algorithm to RS256
JWT_ALGORITHM = "RS256"
JWT_DECODE_ALGORITHMS = ["RS256"]

# Dynamically fetch public key from Keycloak JWKS URL
jwks_url = "http://host.docker.internal:8080/realms/master/protocol/openid-connect/certs"

def fetch_keycloak_rs256_public_cert():
    with urllib.request.urlopen(jwks_url) as response:
        jwks = json.load(response)
    # Uses the second key
    return RSAAlgorithm.from_jwk(json.dumps(jwks["keys"][1]))

JWT_PUBLIC_KEY = fetch_keycloak_rs256_public_cert()

def get_rls_model():
    from superset import db
    from superset.connectors.sqla.models import RowLevelSecurityFilter
    return db, RowLevelSecurityFilter
class CustomSecurityManager(SupersetSecurityManager):
    def map_keycloak_role(self, kc_role: str) -> str | None:
        """
        Map Keycloak roles to Superset roles dynamically.
        """
        mapping = {
            "KeycloakAdmin": "Admin",
            "KeycloakUser": "Gamma",
        }
        
        return mapping.get(kc_role)
    
    def oauth_user_info(self, provider, response=None):
        if provider == "keycloak":
            user_info = self.oauth_remotes[provider].get("userinfo").json()
            print(f">>> OAuth user info: {user_info}")
             # Handle both formats:
            keycloak_roles = (
                user_info.get("roles")
                or user_info.get("realm_access", {}).get("roles")
                or []
            )
            print(f">>> keycloak_roles: {keycloak_roles}")
            return {
                "username": user_info.get("preferred_username"),
                "email": user_info.get("email"),
                "first_name": user_info.get("given_name"),
                "last_name": user_info.get("family_name"),
            }
        return super().oauth_user_info(provider, response)

CUSTOM_SECURITY_MANAGER = CustomSecurityManager

# ------------------------------
# Guest Token Blueprint
# ------------------------------
guest_api_bp = Blueprint(
    "guest_api", __name__, url_prefix="/api/v1/guest"
)

@guest_api_bp.route("/guest_token_sso", methods=["POST"])
def guest_token_sso():
    sm: SupersetSecurityManager = current_app.appbuilder.sm
    data = request.json
    keycloak_jwt = data.get("jwt")
    dashboard_ids = data.get("dashboard_ids")
    if not keycloak_jwt or not dashboard_ids:
        return jsonify({"error": "jwt and dashboard_ids required"}), 400
    try:
        user_info = jwt.decode(
            keycloak_jwt,
            JWT_PUBLIC_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False}  # Skip audience check if needed
        )
    except jwt.PyJWTError as e:
        return jsonify({"error": f"invalid token: {str(e)}"}), 401
    
    username = user_info.get("preferred_username")

    user = sm.get_user_by_username(username)
    if not user:
        return jsonify({"error": "user not found"}), 404

    roles = [role.name for role in user.roles]

    user_rls = []
    db, RowLevelSecurityFilter = get_rls_model()
    for rule in db.session.query(RowLevelSecurityFilter).all():
        rule_roles = [role.name for role in rule.roles]
        if set(roles) & set(rule_roles):
            for table in rule.tables:
                user_rls.append({
                    "dataset": table.id,
                    "clause": rule.clause
                })
    resources = [{"type": "dashboard", "id": dash_id} for dash_id in dashboard_ids]
    token = sm.create_guest_access_token(
        user={"username": user.username},
        resources=resources,
        rls=user_rls,
    )

    return jsonify({"username": user.username, "roles": roles, "rls_rules": user_rls, "guest_token": token})

BLUEPRINTS = [guest_api_bp]
#
# Optionally import superset_config_docker.py (which will have been included on
# the PYTHONPATH) in order to allow for local settings to be overridden
#
try:
    import superset_config_docker
    from superset_config_docker import *  # noqa

    logger.info(
        f"Loaded Your Docker configuration at " f"[{superset_config_docker.__file__}]"
    )
except ImportError:
    logger.info("Using default Docker config...")
