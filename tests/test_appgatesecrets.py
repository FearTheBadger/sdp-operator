import pytest
from typedload.exceptions import TypedloadException

from appgate.attrs import APPGATE_LOADER, K8S_LOADER, K8S_DUMPER, APPGATE_DUMPER
from appgate.secrets import get_appgate_secret, AppgateSecretSimple, AppgateSecretK8S, \
    AppgateSecretException, AppgateSecretPlainText
from tests.utils import load_test_open_api_spec, ENCRYPTED_PASSWORD, \
    FERNET_CIPHER, KEY


def test_write_only_password_attribute_dump():
    EntityTest2 = load_test_open_api_spec().entities['EntityTest2'].cls
    e = EntityTest2(fieldOne='1234567890',
                    fieldTwo='this is write only',
                    fieldThree='this is a field')
    e_data = {
        'fieldOne': '1234567890',
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    assert K8S_DUMPER.dump(e) == e_data
    e_data = {
        'fieldOne': '1234567890',
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    assert APPGATE_DUMPER.dump(e) == e_data


def test_write_only_password_attribute_load():
    e_data = {
        'fieldOne': ENCRYPTED_PASSWORD,  # password
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    EntityTest2 = load_test_open_api_spec().entities['EntityTest2'].cls

    e = APPGATE_LOADER.load(e_data, None, EntityTest2)
    # writeOnly passwords are not loaded from Appgate
    assert e.fieldOne is None
    assert e.fieldTwo is None
    assert e.fieldThree == 'this is a field'
    # writeOnly passwords are not compared
    assert e == EntityTest2(fieldOne='wrong-password',
                            fieldTwo='some value',
                            fieldThree='this is a field')
    # normal fields are compared
    assert e != EntityTest2(fieldOne=None,
                            fieldTwo=None,
                            fieldThree='this is a field with a different value')

    # normal writeOnly fields are not compared when compare_secrets is True
    assert e == EntityTest2(fieldOne=None,
                                                    fieldTwo='some value',
                                                    fieldThree='this is a field')

    e = K8S_LOADER.load(e_data, None, EntityTest2)
    # writeOnly password fields are loaded from K8S
    assert e.fieldOne == '1234567890'  # decrypted password
    assert e.fieldTwo == 'this is write only'
    assert e.fieldThree == 'this is a field'
    # writeOnly password fields are not compared by default
    assert e == EntityTest2(fieldOne=None,
                            fieldTwo=None,
                            fieldThree='this is a field')
    assert e != EntityTest2(fieldOne=None,
                            fieldTwo=None,
                            fieldThree='this is a field with a different value')


def test_get_appgate_secret_plain_text():
    value = 'aaaaaa'
    secret = get_appgate_secret(value, None, lambda x: ENCRYPTED_PASSWORD)
    assert isinstance(secret, AppgateSecretPlainText)


def test_get_appgate_secret_simple():
    value = 'aaaaaa'
    secret = get_appgate_secret(value, FERNET_CIPHER, lambda x: ENCRYPTED_PASSWORD)
    assert isinstance(secret, AppgateSecretSimple)


def test_get_appgate_secret_k8s_simple():
    value = {
        'type': 'k8s/secret',
        'password': 'secret1'
    }
    secret = get_appgate_secret(value, FERNET_CIPHER, lambda x: ENCRYPTED_PASSWORD)
    assert isinstance(secret, AppgateSecretK8S)


def exception():
    value = {
        'some': 'value'
    }
    with pytest.raises(AppgateSecretException):
        get_appgate_secret(value, FERNET_CIPHER, lambda x: ENCRYPTED_PASSWORD)


def test_get_appgate_secret_simple_load():
    EntityTest2 = load_test_open_api_spec(secrets_key=KEY,
                                          reload=True).entities['EntityTest2'].cls
    data = {
        'fieldOne': ENCRYPTED_PASSWORD,
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    e = K8S_LOADER.load(data, None, EntityTest2)
    # Password is decrypted
    assert e.fieldOne == '1234567890'
    assert e.appgate_metadata.passwords == {
        'fieldOne': ENCRYPTED_PASSWORD
    }


def test_get_appgate_secret_simple_load_no_cipher():
    EntityTest2 = load_test_open_api_spec(secrets_key=None,
                                          reload=True).entities['EntityTest2'].cls
    data = {
        'fieldOne': ENCRYPTED_PASSWORD,
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    e = K8S_LOADER.load(data, None, EntityTest2)
    # We don't try to decrypt the password, use it as we get it
    assert e.fieldOne == ENCRYPTED_PASSWORD
    assert e.appgate_metadata.passwords == {
        'fieldOne': ENCRYPTED_PASSWORD
    }


def _k8s_get_secret(name: str, key: str) -> str:
    k8s_secrets = {
        'secret-storage-1': {
            'field-one': '1234567890-from-k8s'
        }
    }
    if name in k8s_secrets and key in k8s_secrets[name]:
        return k8s_secrets[name][key]
    raise Exception(f'Unable to get secret: {name}.{key}')


def test_get_appgate_secret_k8s_simple_load():
    EntityTest2 = load_test_open_api_spec(reload=True,
                                          k8s_get_secret=_k8s_get_secret).entities['EntityTest2'].cls
    data = {
        'fieldOne': {
            'type': 'k8s/secret',
            'name': 'secret-storage-1',
            'key': 'field-one'
        },
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    e = K8S_LOADER.load(data, None, EntityTest2)
    # Password is coming from k8s secrets
    assert e.fieldOne == '1234567890-from-k8s'
    assert e.appgate_metadata.passwords == {
        'fieldOne': data['fieldOne']
    }


def test_get_appgate_secret_k8s_simple_load_missing_key():
    EntityTest2 = load_test_open_api_spec(reload=True,
                                          k8s_get_secret=_k8s_get_secret).entities['EntityTest2'].cls
    data = {
        'fieldOne': {
            'type': 'k8s/secret',
            'name': 'secret-storage',
            'key': 'field-one'
        },
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    with pytest.raises(TypedloadException, match='Unable to get secret: secret-storage.field-one'):
        K8S_LOADER.load(data, None, EntityTest2)


def test_get_secret_read_entity_without_password():
    EntityTest2 = load_test_open_api_spec(reload=True,
                                          k8s_get_secret=_k8s_get_secret).entities['EntityTest2'].cls
    data = {
        'fieldTwo': 'this is write only',
        'fieldThree': 'this is a field',
    }
    e = K8S_LOADER.load(data, None, EntityTest2)
    # Password is coming from k8s secrets
    assert e.fieldOne is None
