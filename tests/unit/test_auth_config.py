import pytest

from app.core.config import CorsSettings


@pytest.mark.parametrize('value', [
    '*', 'https://*.example.test', 'https://example.test/path',
    'https://user@example.test', 'null', '', 'https://example.test:99999',
])
def test_cors_rejects_non_origins(value):
    with pytest.raises(ValueError):
        _ = CorsSettings(_env_file=None, cors_origins=value).origins


def test_cors_reads_dotenv_without_database_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv('CORS_ORIGINS', raising=False)
    dotenv = tmp_path / '.env'
    dotenv.write_text('CORS_ORIGINS=https://app.example.test\n', encoding='utf-8')
    assert CorsSettings(_env_file=dotenv).origins == ['https://app.example.test']
