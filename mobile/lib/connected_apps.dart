import 'ios_settings.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'live_search.dart';

enum LinkedApp { maps, drive, gmail, grab, be, green }

const appNames = {LinkedApp.maps:'Google Maps', LinkedApp.drive:'Google Drive', LinkedApp.gmail:'Gmail', LinkedApp.grab:'Grab', LinkedApp.be:'be', LinkedApp.green:'Xanh SM'};
const appPackages = {LinkedApp.maps:'com.google.android.apps.maps', LinkedApp.drive:'com.google.android.apps.docs', LinkedApp.gmail:'com.google.android.gm', LinkedApp.grab:'com.grabtaxi.passenger', LinkedApp.be:'xyz.be.customer', LinkedApp.green:'com.gsm.customer'};

LinkedApp? requestedApp(String text) {
  final q=foldVietnamese(text);
  if (!RegExp(r'^(?:hay |vui long )?(?:mo|tim|tra cuu|soan|goi|dat)\b').hasMatch(q)) return null;
  if (RegExp(r'\b(gmail|email|thu dien tu)\b').hasMatch(q)) return LinkedApp.gmail;
  if (RegExp(r'\b(?:google )?drive\b').hasMatch(q)) return LinkedApp.drive;
  if (RegExp(r'\bgrab\b').hasMatch(q)) return LinkedApp.grab;
  if (RegExp(r'^(?:hay |vui long )?mo (?:be|bee)\b|\b(?:xe|app|ung dung) (?:be|bee)\b').hasMatch(q)) return LinkedApp.be;
  if (RegExp(r'\bxanh sm\b').hasMatch(q)) return LinkedApp.green;
  return null;
}

Uri mapSearch(String query) => Uri.https('www.google.com','/maps/search/',{'api':'1','query':query.trim()});
Uri mapDirections(String destination) => Uri.https('www.google.com','/maps/dir/',{'api':'1','destination':destination.trim()});
Uri driveSearch(String query) => query.trim().isEmpty ? Uri.https('drive.google.com','/drive/u/0/my-drive') : Uri.https('drive.google.com','/drive/u/0/search',{'q':query.trim()});
Uri emailDraft(String to,String subject,String body) => Uri(scheme:'mailto',path:to.trim(),query:['subject=${Uri.encodeComponent(subject)}','body=${Uri.encodeComponent(body)}'].join('&'));

class ConnectedAppsPage extends StatefulWidget {
  final LinkedApp initialApp;
  final String initialRequest;
  const ConnectedAppsPage({super.key,this.initialApp=LinkedApp.maps,this.initialRequest=''});
  @override
  State<ConnectedAppsPage> createState()=>_ConnectedAppsPageState();
}
class _ConnectedAppsPageState extends State<ConnectedAppsPage> {
  static const channel=MethodChannel('vn.chatai/linked_apps');
  final query=TextEditingController(),recipient=TextEditingController(),subject=TextEditingController(),body=TextEditingController();
  late LinkedApp selected;
  bool busy=false;
  String? message;
  @override
  void initState(){super.initState();selected=widget.initialApp;
    if(selected==LinkedApp.drive && RegExp(r'^(?:hãy |vui lòng )?(?:tìm|tra cứu)\b',caseSensitive:false).hasMatch(widget.initialRequest)){query.text=widget.initialRequest.replaceFirst(RegExp(r'^(?:hãy |vui lòng )?(?:tìm|tra cứu)(?: tệp| file)?\s+',caseSensitive:false),'').replaceFirst(RegExp(r'\s+(?:trên |trong )?(?:google )?drive.*$',caseSensitive:false),'').trim();}}
  @override
  void dispose(){for(final c in [query,recipient,subject,body]){c.dispose();}super.dispose();}
  Future<void> open({Uri? uri}) async {
    setState((){busy=true;message=null;});
    try {
      bool opened=false;
      if(uri!=null){opened=await launchUrl(uri,mode:LaunchMode.externalApplication);}
      else {
        try{opened=await channel.invokeMethod<bool>('open',appPackages[selected])??false;}on MissingPluginException{opened=false;}
        if(!opened && mounted){
          final install=await showDialog<bool>(context:context,builder:(c)=>IosAlertDialog(title:Text('Chưa mở được ${appNames[selected]}'),content:const Text('Ứng dụng có thể chưa được cài. Mở trang Google Play để kiểm tra?'),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:const Text('Hủy')),FilledButton(onPressed:()=>Navigator.pop(c,true),child:const Text('Google Play'))]));
          if(install==true)opened=await launchUrl(Uri.https('play.google.com','/store/apps/details',{'id':appPackages[selected]!}),mode:LaunchMode.externalApplication);
        }
      }
      if(mounted)setState(()=>message=opened?'Đã chuyển yêu cầu sang ứng dụng ngoài. Chat AI chưa xác nhận thao tác bên đó đã hoàn tất.':'Chưa mở được ứng dụng. Kiểm tra ứng dụng đã cài hoặc thử lại.');
    }catch(_){if(mounted)setState(()=>message='Chưa mở được ứng dụng. Không có email hay chuyến xe nào được Chat AI gửi/đặt.');}
    finally{if(mounted)setState(()=>busy=false);}
  }
  @override
  Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('Ứng dụng & liên kết')),body:IosPageList(title:'Ứng dụng',subtitle:'Tiếp tục công việc trong ứng dụng bạn dùng mỗi ngày.',children:[
    const Text('Mở ứng dụng để tiếp tục công việc. Chat AI chưa có quyền đọc Drive/Gmail và không tự đặt xe hoặc gửi thư.'),
    if(widget.initialRequest.isNotEmpty) Padding(padding:const EdgeInsets.only(top:12),child:Text('Yêu cầu: ${widget.initialRequest}')),
    const SizedBox(height:16),
    IosPicker<LinkedApp>(title:'Ứng dụng',value:selected,options:appNames,onChanged:busy?null:(value)=>setState((){selected=value;message=null;})),
    const SizedBox(height:20),
    if(selected==LinkedApp.maps)...[
      TextField(controller:query,decoration:const InputDecoration(labelText:'Địa điểm hoặc điểm đến',hintText:'Ví dụ: Sân bay Nội Bài'),maxLength:300),
      FilledButton(onPressed:busy?null:(){if(query.text.trim().isEmpty){setState(()=>message='Hãy nhập địa điểm.');return;}open(uri:mapSearch(query.text));},child:const Text('Tìm trên Google Maps')),
      OutlinedButton(onPressed:busy?null:(){if(query.text.trim().isEmpty){setState(()=>message='Hãy nhập điểm đến.');return;}open(uri:mapDirections(query.text));},child:const Text('Mở chỉ đường')),
    ]else if(selected==LinkedApp.drive)...[
      TextField(controller:query,decoration:const InputDecoration(labelText:'Tên tệp cần tìm trên Drive'),maxLength:300),
      FilledButton(onPressed:busy?null:()=>open(uri:driveSearch(query.text)),child:const Text('Mở Drive / tìm tệp')),
      const Text('Bạn chọn tài khoản và mở tệp trong Drive. Chat AI chưa đọc, tải lên hay tóm tắt tệp từ tài khoản Google của bạn.'),
    ]else if(selected==LinkedApp.gmail)...[
      TextField(controller:recipient,keyboardType:TextInputType.emailAddress,decoration:const InputDecoration(labelText:'Email người nhận'),maxLength:254),
      TextField(controller:subject,decoration:const InputDecoration(labelText:'Tiêu đề'),maxLength:200),
      TextField(controller:body,decoration:const InputDecoration(labelText:'Nội dung bản nháp'),minLines:3,maxLines:8,maxLength:5000),
      FilledButton(onPressed:busy?null:(){if(!RegExp(r'^[^\s@,;\r\n]+@[^\s@,;\r\n]+\.[^\s@,;\r\n]+$').hasMatch(recipient.text.trim())){setState(()=>message='Nhập một địa chỉ email người nhận hợp lệ.');return;}open(uri:emailDraft(recipient.text,subject.text,body.text));},child:const Text('Mở ứng dụng email để xem và gửi')),
      const Text('Ứng dụng email mặc định sẽ mở bản nháp. Bạn kiểm tra nội dung và tự bấm Gửi; Chat AI không tự gửi.'),
    ]else...[
      Text('Mở ${appNames[selected]} để chọn điểm đón, điểm đến và xem giá. Chưa có tích hợp đặt chuyến hoặc truyền điểm đến tự động.'),
      const SizedBox(height:12),FilledButton(onPressed:busy?null:()=>open(),child:Text('Mở ${appNames[selected]}')),
    ],
    const SizedBox(height:12),OutlinedButton(onPressed:busy?null:()=>open(),child:Text('Mở ứng dụng ${appNames[selected]}')),
    if(message!=null)Padding(padding:const EdgeInsets.symmetric(vertical:16),child:Text(message!)),
    const Divider(),
    const ListTile(leading:Icon(Icons.lock_outline),title:Text('Drive / Gmail: chưa kết nối tài khoản'),subtitle:Text('Đọc hoặc làm việc trực tiếp trong Chat AI cần thiết lập OAuth Google. Không nhập mật khẩu Google vào Chat AI.')),
  ]));
}
