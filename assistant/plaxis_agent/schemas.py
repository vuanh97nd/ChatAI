"""Function-calling inputs: reject unknown fields, non-finite values and code."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class Inspect(Input):
    version: Literal['2d', '3d']


class Material(Input):
    version: Literal['2d', '3d']
    name: str = Field(min_length=1, max_length=80, pattern=r'^[\w .-]+$')
    gamma_unsat: float = Field(gt=0, le=35, description='Trọng lượng riêng không bão hòa, kN/m³')
    gamma_sat: float = Field(gt=0, le=40, description='Trọng lượng riêng bão hòa, kN/m³')
    e_ref: float = Field(gt=0, le=1e9, description='Young E tham chiếu của Mohr-Coulomb, kPa')
    nu: float = Field(ge=0, lt=.5)
    c: float = Field(ge=0, le=1e6, description='Lực dính hữu hiệu, kPa')
    phi: float = Field(ge=0, lt=90, description='Góc ma sát hữu hiệu, độ')
    psi: float = Field(ge=0, lt=90, description='Góc giãn nở, độ')
    drainage: Literal['Drained', 'Undrained A']
    source: str = Field(min_length=1, max_length=500, description='Nguồn dữ liệu; không tự đoán số liệu manual')

    @model_validator(mode='after')
    def consistency(self) -> 'Material':
        if self.gamma_sat < self.gamma_unsat or self.psi > self.phi:
            raise ValueError('Cần gamma_sat >= gamma_unsat và psi <= phi.')
        return self


class Layer(Input):
    version: Literal['2d']
    thickness: float = Field(gt=0, le=1000, description='Bề dày lớp mới, m; cần borehole có sẵn')
    source: str = Field(min_length=1, max_length=500)


class Vertex(Input):
    x: float = Field(ge=-1e4, le=1e4, description='Toạ độ X, m')
    y: float = Field(ge=-1e4, le=1e4, description='Toạ độ Y (2D) hoặc Z (3D), m')


class Contour(Input):
    version: Literal['2d']
    shape: Literal['rectangle', 'polygon'] = Field(description='rectangle = soilcontour xmin ymin xmax ymax (4 đỉnh trục XY); polygon = PLAXIS polygon lệnh với 3+ đỉnh thứ tự')
    vertices: list[Vertex] = Field(min_length=3, max_length=64, description='Danh sách đỉnh theo thứ tự. rectangle cần đúng 4 đỉnh tạo chữ nhật trục XY.')
    source: str = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def check_shape(self) -> 'Contour':
        if self.shape == 'rectangle':
            if len(self.vertices) != 4:
                raise ValueError('rectangle cần đúng 4 đỉnh.')
            xs = sorted({round(v.x, 6) for v in self.vertices})
            ys = sorted({round(v.y, 6) for v in self.vertices})
            if len(xs) != 2 or len(ys) != 2:
                raise ValueError('rectangle: 4 đỉnh phải thẳng trục XY, chỉ có 2 giá trị X và 2 giá trị Y khác nhau.')
        return self


class Check(Input):
    ref: str = Field(pattern=r'^g\.(?:Project\.(?:ModelType|UnitLength|UnitForce)|[A-Za-z][A-Za-z0-9_]*\.(?:Head|ERef|gammaUnsat|gammaSat|nu|cRef|phi|psi))$')
    expected: float | str
    tolerance: float = Field(default=1e-6, ge=0, le=1)


class Calculate(Input):
    version: Literal['2d', '3d']
    checks: list[Check] = Field(min_length=1, max_length=100, description='Giá trị kỳ vọng có nguồn; verify ngay trước calculate trong cùng lô')
    source: str = Field(min_length=1, max_length=500)


class Criterion(Input):
    metric: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z][A-Za-z0-9_]*$')
    operator: Literal['le', 'ge']
    target: float
    unit: str = Field(min_length=1, max_length=30)


class JobRequest(Input):
    prompt: str = Field(min_length=1, max_length=12000)
    version: Literal['2d', '3d']
    max_steps: int = Field(default=12, ge=1, le=40)
    project_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[\w.-]+$")
    criteria: list[Criterion] = Field(default_factory=list, max_length=20)
    max_reviews: int = Field(default=2, ge=1, le=4)
    model_tier: Literal['flash', 'reasoning', 'auto'] = Field(default='auto')



class GeoCalculation(Input):
    version: Literal['2d', '3d']
    formula: Literal['bearing_capacity', 'settlement', 'earth_pressure', 'mohr_coulomb', 'spt_correlation', 'slope_stability']
    params: dict = Field(description='JSON parameters in SI units: lengths m, stress kPa, unit weight kN/m³, angles degrees; no code.')

    @model_validator(mode='after')
    def validate_parameters(self) -> 'GeoCalculation':
        import json
        from assistant.geo_solver import _finite_data
        required = {
            'settlement': {'H', 'e0', 'Cc', 'sigma0', 'delta_sigma'},
            'bearing_capacity': {'c', 'phi', 'gamma', 'B', 'Df'},
            'earth_pressure': {'gamma', 'H', 'phi'},
            'slope_stability': {'c', 'phi', 'gamma', 'H', 'slope_angle'},
            'spt_correlation': {'N'}, 'mohr_coulomb': {'c', 'phi'},
        }
        if not required[self.formula].issubset(self.params):
            raise ValueError('Thiếu tham số: ' + ', '.join(sorted(required[self.formula] - self.params.keys())))
        if len(json.dumps(self.params, allow_nan=False)) > 4000:
            raise ValueError('Parameters exceed 4000 characters.')
        _finite_data(self.params)
        return self


class DocumentIndex(Input):
    path: str = Field(min_length=1, max_length=1000)
