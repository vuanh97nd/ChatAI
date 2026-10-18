import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/cloud_voice.dart';
import 'voice_test.dart' show FakeVoice;
void main(){
 TestWidgetsFlutterBinding.ensureInitialized();
 test('available device recognition bypasses recording and server transcription',() async {
  final device=FakeVoice();final api=ChatApi();final modes=<String>[];final statuses=<String>[];
  final engine=CloudVoiceEngine(api,deviceRecognizer:device,microphonePermission:() async=>true,onRecognitionMode:modes.add);
  expect(await engine.initialize(statuses.add,(_)=>fail('Unexpected recognition error')),isTrue);
  expect(engine.recordsAudio,isFalse);expect(modes,['Nhận dạng Android']);
  expect(await engine.locales(),contains('vi_VN'));
  var heard='';await engine.listen('vi_VN',(text)=>heard=text);
  device.recognition!('Xin chào');expect(heard,'Xin chào');
  device.status!('done');expect(statuses,['done']);
  await engine.finish();expect(device.cancels,greaterThan(0));
  await engine.close();api.close();
 });
 test('microphone denial never starts native recognition or requests transcription',() async {
  final device=FakeVoice();final api=ChatApi();final errors=<String>[];
  final engine=CloudVoiceEngine(api,deviceRecognizer:device,microphonePermission:() async=>false);
  expect(await engine.initialize((_){},errors.add),isFalse);
  expect(device.status,isNull);expect(errors,['microphone_permission_denied']);
  await engine.close();api.close();
 });
 test('native service permission error selects online recognition for explicit retry',() async {
  final device=FakeVoice();final api=ChatApi();final errors=<String>[];
  final engine=CloudVoiceEngine(api,deviceRecognizer:device,microphonePermission:() async=>true);
  await engine.initialize((_){},errors.add);
  device.recognitionError!('error_permission');
  expect(engine.preferDeviceRecognition,isFalse);expect(errors,['error_permission']);
  await engine.close();api.close();
 });

}
