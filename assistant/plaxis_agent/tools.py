"""Allowlisted wrappers. The model never supplies API command names or Python."""
import json
import hashlib
from typing import Any
from pydantic import BaseModel, ValidationError
from .schemas import Inspect, Material, Layer, Calculate, GeoCalculation, Contour
from .utils import logger

MODELS: dict[str, type[BaseModel]] = {
    'plaxis_safe_geo_calculate': GeoCalculation,
    'plaxis_safe_inspect': Inspect, 'plaxis_safe_material': Material,
    'plaxis_safe_layer': Layer, 'plaxis_safe_calculate': Calculate,
    'plaxis_safe_contour': Contour,
}
_MAX_RESULT_CHARS = 2000

# Compact descriptions (~80 chars avg) trim schema tokens; enables prefix-cache hits on DeepSeek Flash.
DESCRIPTIONS = {
    'plaxis_safe_geo_calculate': 'Tính địa kỹ thuật Python: settlement(H,e0,Cc,sigma0,delta_sigma), bearing_capacity(c,phi,gamma,B,Df), earth_pressure(gamma,H,phi), mohr_coulomb(c,phi,sigma_n). SI m/kN/kPa/độ. Không thao tác PLAXIS.',
    'plaxis_safe_inspect': 'Đọc trạng thái PLAXIS Input; bắt buộc trước mọi thao tác ghi.',
    'plaxis_safe_material': 'Tạo vật liệu Mohr-Coulomb (SI kN/m/kPa); chỉ Drained hoặc Undrained A. Cần nguồn dữ liệu.',
    'plaxis_safe_layer': 'Thêm lớp đất 2D theo bề dày vào borehole đã có; chưa gán vật liệu.',
    'plaxis_safe_calculate': 'Verify thuộc tính kỳ vọng rồi calculate trong cùng lô.',
    'plaxis_safe_contour': 'Tạo soil contour/polygon 2D từ danh sách đỉnh (x,y). rectangle=soilcontour 4 đỉnh trục XY; polygon=PLAXIS polygon 3+ đỉnh.',
}


def _truncate_result(result: dict[str, Any]) -> dict[str, Any]:
    if len(json.dumps(result, ensure_ascii=False, default=str)) <= _MAX_RESULT_CHARS:
        return result
    trimmed = {k: result[k] for k in ('ok', 'error', 'uncertain', 'metrics', 'source', 'material_verified') if k in result}
    trimmed['_truncated'] = True
    trimmed['_hint'] = 'Kết quả bị cắt; dùng inspect lại để đọc chi tiết nếu cần.'
    return trimmed


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
        if name == 'plaxis_safe_geo_calculate':
            from assistant.geo_solver import geo_calculate
            result = geo_calculate(data['formula'], json.dumps(data['params']))
            units = {'S_m': 'm', 'S_mm': 'mm', 'FS': '1', 'qu_kPa': 'kPa', 'tau_failure_kPa': 'kPa'}
            metrics = {key: {'value': result[key], 'unit': unit} for key, unit in units.items() if key in result}
            if 'qa_kPa (FS=3)' in result:
                metrics['qa_kPa'] = {'value': result['qa_kPa (FS=3)'], 'unit': 'kPa'}
            return {'ok': 'error' not in result, 'metrics': metrics, **result}
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
        elif name == 'plaxis_safe_contour':
            vertices = [(v['x'], v['y']) for v in data['vertices']]
            if data['shape'] == 'rectangle':
                xs = sorted({round(x, 6) for x, _ in vertices})
                ys = sorted({round(y, 6) for _, y in vertices})
                rows = [{'command': 'gotostructures'},
                        {'command': 'verify_model', 'args': [json.dumps([
                            {'ref':'g.Project.UnitLength','expected':'m'}])]},
                        {'command': 'soilcontour', 'args': [xs[0], ys[0], xs[1], ys[1]]},
                        {'command': 'read', 'args': [{'ref': 'g.SoilContour'}]}]
            else:
                # Reject duplicate consecutive vertices to avoid PLAXIS parser rejecting zero-length segments.
                seen = []
                for v in vertices:
                    if seen and seen[-1] == v:
                        raise ValueError('polygon có đỉnh trùng liên tiếp.')
                    seen.append(v)
                rows = [{'command': 'gotostructures'},
                        {'command': 'verify_model', 'args': [json.dumps([
                            {'ref':'g.Project.UnitLength','expected':'m'}])]},
                        {'command': 'polygon', 'args': [list(v) for v in seen]},
                        {'command': 'read', 'args': [{'ref': 'g.Polygons'}]}]
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
        return _truncate_result(result)
    except (ValidationError, ValueError) as error:
        return {'ok': False, 'not_executed': True, 'error': str(error)[:2000]}
    except Exception as error:
        logger.exception('tool_failed name=%s', name)
        return {'ok': False, 'uncertain': True, 'error': str(error)[:1000],
                'note': 'Không tự gọi lại; đọc trạng thái PLAXIS trước khi sửa.'}
