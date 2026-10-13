"""Inspect installed GeoStudio API; optionally read a temporary project copy.

No Save/Set/Add/Delete/Solve calls. Run with Chat AI's Windows Python 3.12.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path)
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
                project = interface.OpenProject(str(working))
                report['connected'] = True
                report['source'] = str(source)
                try:
                    response = project.Get(pb.GetRequest(), timeout=30)
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
