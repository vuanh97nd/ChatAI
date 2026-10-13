"""Inspect installed GeoStudio API; optionally read a temporary project copy.

No Save/Set/Add/Delete/Solve calls. Run with Chat AI's Windows Python 3.12.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import tempfile
import re
import zipfile
import xml.etree.ElementTree as ET


def analysis_names(path):
    with zipfile.ZipFile(path) as archive:
        roots = [entry for entry in archive.infolist()
                 if '/' not in entry.filename and '\\' not in entry.filename
                 and entry.filename.lower().endswith('.xml')]
        if len(roots) != 1 or roots[0].file_size > 20 * 1024 ** 2:
            raise ValueError('GSZ needs one root project XML, at most 20 MiB.')
        data = archive.read(roots[0])
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('Unsupported XML declarations.')
    root = ET.fromstring(data)
    return [name for item in root.findall('./Analyses/Analysis')
            if (name := item.findtext('Name'))]


def point_object(path, analysis):
    """Use the documented Points[id] form with an ID from the saved model.

    A missing/ambiguous geometry is a diagnostic, not a reason to invent IDs.
    """
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist()
                 if '/' not in name and '\\' not in name and name.lower().endswith('.xml')]
        root = ET.fromstring(archive.read(names[0]))
    geometries = root.findall('./Geometries/Geometry')
    item = next(item for item in root.findall('./Analyses/Analysis')
                if item.findtext('Name') == analysis)
    geometry_id = item.findtext('GeometryId') or item.findtext('GeometryID')
    if geometry_id:
        geometries = [g for g in geometries if g.findtext('ID') == geometry_id]
    if len(geometries) != 1:
        raise ValueError('Ambiguous geometry: supply --object from the API documentation.')
    for point in geometries[0].findall('./Points/Point'):
        ident = point.get('ID') or point.findtext('ID')
        if ident and ident.isdecimal():
            return 'CurrentAnalysis.GeometryItems.Points[' + ident + ']'
    raise ValueError('No saved point ID found; supply --object from the API documentation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--analysis', help='Exact analysis name from the project')
    parser.add_argument('--object', help='Object path from API documentation, if needed')
    parser.add_argument('--output', type=Path, default=Path('data/geostudio-api-probe.json'))
    args = parser.parse_args()
    report = {'connected': False, 'solved': False, 'errors': []}
    try:
        interface = importlib.import_module('gsi.interface')
        pb = importlib.import_module('gsi.protobuf.gsi_project_pb2')
        from google.protobuf.json_format import MessageToDict
        report['required_version'] = interface.REQUIRED_GEOSTUDIO_VERSION
        report['requests'] = {}
        for name, descriptor in pb.DESCRIPTOR.message_types_by_name.items():
            if name.endswith('Request'):
                report['requests'][name] = [
                    {'name': field.name, 'type': field.type,
                     'repeated': field.label == field.LABEL_REPEATED,
                     'enum': field.enum_type.full_name if field.enum_type else None}
                    for field in descriptor.fields]
        report['enums'] = {}
        for module in ('gsi_Result_Type_pb2', 'gsi_DataParam_Type_pb2'):
            definition = importlib.import_module('gsi.protobuf.' + module)
            report['enums'][module] = {
                name: {value.name: value.number for value in descriptor.values}
                for name, descriptor in definition.DESCRIPTOR.enum_types_by_name.items()}
        if args.project:
            source = args.project.resolve(strict=True)
            if source.suffix.lower() != '.gsz':
                raise ValueError('Project must be a saved .gsz file.')
            # ConnectionManager owns a separate temporary copy, never the user's
            # currently opened file. Close before removing its working directory.
            with tempfile.TemporaryDirectory(prefix='ChatAI-GeoStudio-Probe-') as folder:
                working = Path(folder) / source.name
                shutil.copy2(source, working)
                names = analysis_names(working)
                report['analyses'] = names
                selected = args.analysis or (names[0] if len(names) == 1 else None)
                if not selected or selected not in names:
                    raise ValueError('Use --analysis with one of these exact names: ' + json.dumps(names, ensure_ascii=False))
                project = interface.OpenProject(str(working))
                report['connected'] = True
                report['source'] = str(source)
                try:
                    request = pb.GetRequest(analysis=selected,
                                            object=args.object or point_object(working, selected))
                    report['get_request'] = MessageToDict(request, preserving_proto_field_name=True)
                    response = project.Get(request, timeout=30)
                    report['get_response'] = MessageToDict(response, preserving_proto_field_name=True)
                    report['read_succeeded'] = True
                finally:
                    project.Close()
    except Exception as error:
        report['errors'].append({'type': type(error).__name__, 'message': str(error)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(args.output.resolve()))
    print('Connected:', report['connected'], '| Read:', report.get('read_succeeded', False))
    if report['errors']:
        print(json.dumps(report['errors'], ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
