"""
Connector factory — instantiates the right connector for a MediaSource.
"""

from __future__ import annotations

from app.connectors.base import AbstractConnector
from app.connectors.ftp import FTPConnector
from app.connectors.local import LocalConnector
from app.connectors.smb import SMBConnector


def get_connector(source, credential=None) -> AbstractConnector:
    """
    Return the appropriate connector for *source*.

    Args:
        source: MediaSource ORM instance
        credential: SourceCredential ORM instance or None
    """
    if source.source_type == "local":
        return LocalConnector(source.path)

    if source.source_type == "smb":
        if not credential:
            raise ValueError("SMB source requires credentials")
        from app.core import encryption
        pw = ""
        if credential.password_enc:
            pw = encryption.decrypt(credential.password_enc)
        return SMBConnector(
            host=credential.host,
            share=credential.share or "",
            base_path=source.path,
            username=credential.username or "",
            password=pw,
            domain=credential.domain or "",
            port=credential.port or 445,
        )

    if source.source_type == "ftp":
        if not credential:
            raise ValueError("FTP source requires credentials")
        from app.core import encryption
        pw = ""
        if credential.password_enc:
            pw = encryption.decrypt(credential.password_enc)
        return FTPConnector(
            host=credential.host,
            port=credential.port or 21,
            base_path=source.path,
            username=credential.username or "anonymous",
            password=pw,
        )

    raise ValueError(f"Unknown source_type: {source.source_type!r}")
