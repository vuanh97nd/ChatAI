"""Allowlisted wrappers. The model never supplies API command names or Python."""
import json
import hashlib
from typing import Any
from pydantic import BaseModel, ValidationError
from .schemas import Inspect, Material, Layer, Calculate
from .utils import logger

MODELS: dict[str, type[BaseModel]] = {
    'plaxis_safe_inspect': Inspect, 'plaxis_safe_material': Material,
    'plaxis_safe_layer': Layer, 'plaxis_safe_calculate': Calculate,
}
DESCRIPTIONS = {
    'plaxis_safe_inspect': 'Đọc trạng thái PLAXIS Input hiện tại; kiểm tra trước khi ghi, không tạo mới dự án.',
    'plaxis_safe_material': 'Tạo vật liệu Mohr-Coulomb theo số liệu có nguồn, SI kN/m/kPa; dùng kết quả tên API thật để đọc lại. Không dùng cho HS hay Undrained B.',
    'plaxis_safe_layer': 'Thêm một lớp đất 2D có bề dày xác định vào borehole đã có; chưa gán vật liệu. Không tự tạo borehole.',
    'plaxis_safe_calculate': 'Đối chiếu các thuộc tính kỳ vọng rồi calculate cùng một lô. Các checks chỉ xác minh phần liệt kê; chưa chứng minh toàn bộ bài đúng manual.',
}


def schemas() -> list[dict[str, Any]]:
    return [{'type': 'function', 'function': {'name': name, 'description': DESCRIPTIONS[name],
            'parameters': model.model_json_schema()}} for name, model in MODELS.items()]


def prepare(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in MODELS:
        raise ValueError('Tool không thuộc danh sách PLAXIS an toàn.')
    value = MODELS[name].model_validate(arguments)
    return {'action': name, 'input': value.model_dump()}


def execute(remote: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate again at the write boundary; never retry an uncertain write."""
    try:
        data = prepare(name, arguments)['input']
        version = data['version']
        alias='safe_mat_'+hashlib.sha256(str(data.get('name','')).encode()).hexdigest()[:12]
        if name == 'plaxis_safe_inspect':
            rows = [{'command': 'read', 'args': [{'ref': 'g.Project'}]}]
        elif name == 'plaxis_safe_material':
            rows = [{'command': 'gotosoil'}, {'command': 'verify_model', 'args': [json.dumps([
                    {'ref':'g.Project.UnitLength','expected':'m'},
                    {'ref':'g.Project.UnitForce','expected':'kN'}])]},
                    {'command': 'ensure_new_material', 'args': [data['name']]},
                    {'command': 'soilmat', 'result': alias},
                    {'command': 'setproperties', 'args': [{'ref': alias},
                     'Identification', data['name'], 'SoilModel', 'Mohr-Coulomb',
                     'DrainageType', data['drainage'], 'gammaUnsat', data['gamma_unsat'],
                     'gammaSat', data['gamma_sat'], 'ERef', data['e_ref'], 'nu', data['nu'],
                     'cRef', data['c'], 'phi', data['phi'], 'psi', data['psi']]},
                    {'command': 'verify_model', 'args': [json.dumps([
                        {'ref':alias+'.'+property_name,'expected':data[input_name]}
                        for property_name,input_name in (
                            ('gammaUnsat','gamma_unsat'),('gammaSat','gamma_sat'),
                            ('ERef','e_ref'),('nu','nu'),('cRef','c'),('phi','phi'),('psi','psi'))])]},
                    {'command': 'read', 'args': [{'ref': alias}]}]
        elif name == 'plaxis_safe_layer':
            rows = [{'command': 'gotosoil'}, {'command': 'verify_model', 'args': [json.dumps([
                    {'ref':'g.Project.UnitLength','expected':'m'},
                    {'ref':'g.Boreholes','expected':1,'kind':'count'}])]},
                    {'command': 'soillayer', 'args': [data['thickness']]},
                    {'command': 'read', 'args': [{'ref': 'g.Soillayers'}]}]
        else:
            rows = [{'command': 'gotostages'},
                    {'command': 'verify_model', 'args': [json.dumps(data['checks'])]},
                    {'command': 'calculate'}, {'command': 'read', 'args': [{'ref': 'g.Phases'}]}]
        logger.info('tool_start name=%s version=%s', name, version)
        result = remote.commit(remote.prepare('plaxis_commands',
            {'version': version, 'target': 'input', 'commands': json.dumps(rows)}))
        result['source'] = data.get('source')
        if name == 'plaxis_safe_material':
            result['material_verified'] = result.get('ok') is True and result.get('model_verified') is True
            result['model_verified'] = False  # Material checks do not verify a whole project.
        logger.info('tool_end name=%s ok=%s uncertain=%s', name, result.get('ok'), result.get('uncertain'))
        return result
    except (ValidationError, ValueError) as error:
        return {'ok': False, 'not_executed': True, 'error': str(error)[:2000]}
    except Exception as error:
        logger.exception('tool_failed name=%s', name)
        return {'ok': False, 'uncertain': True, 'error': str(error)[:1000],
                'note': 'Không tự gọi lại; đọc trạng thái PLAXIS trước khi sửa.'}
