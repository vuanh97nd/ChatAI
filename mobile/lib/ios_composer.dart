import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'provider_icon.dart';
import 'visual_style.dart';

class IosChatComposer extends StatelessWidget {
 final TextEditingController controller;
 final String provider;
 final bool busy,hasAttachments,listening,canChooseProvider;
 final VoidCallback onChanged;
 final ValueChanged<String> onProvider;
 final VoidCallback? onAttach,onMedia,onMicrophone,onAction;
 final List<Widget> attachmentChips;
 const IosChatComposer({super.key,required this.controller,required this.provider,required this.busy,required this.hasAttachments,required this.listening,required this.onChanged,required this.onProvider,this.onAttach,this.onMedia,this.onMicrophone,this.onAction,this.attachmentChips=const [],this.canChooseProvider=true});
 static const names={'openrouter':'OpenRouter','nvidia':'NVIDIA','deepseek_flash':'DeepSeek','cloudflare':'Cloudflare AI','gemini':'Gemini','groq':'Groq'};
 Future<void> chooseProvider(BuildContext context) async {
  final selected=await showCupertinoModalPopup<String>(context:context,builder:(c)=>CupertinoActionSheet(
   title:const Text('Chọn AI'),message:const Text('AI đang chọn tiếp tục dùng các trợ lý chuyên môn tự động.'),
   actions:[for(final entry in names.entries)CupertinoActionSheetAction(onPressed:()=>Navigator.pop(c,entry.key),child:Row(mainAxisAlignment:MainAxisAlignment.center,children:[ProviderIcon(provider:entry.key,size:22),const SizedBox(width:10),Text(entry.value),if(entry.key==provider)...[const SizedBox(width:10),const Icon(CupertinoIcons.check_mark,size:20)]]))],
   cancelButton:CupertinoActionSheetAction(onPressed:()=>Navigator.pop(c),child:const Text('Hủy'))));
  if(selected!=null){HapticFeedback.selectionClick();onProvider(selected);}
 }
 @override
 Widget build(BuildContext context){
  final empty=controller.text.trim().isEmpty&&!hasAttachments;
  final color=Theme.of(context).colorScheme;
  return Padding(padding:const EdgeInsets.fromLTRB(12,6,12,10),child:GlassPanel(radius:BorderRadius.circular(24),child:Padding(
   padding:const EdgeInsets.fromLTRB(5,0,5,5),child:Column(mainAxisSize:MainAxisSize.min,children:[
    Row(children:[Expanded(child:Align(alignment:Alignment.centerLeft,child:CupertinoButton(padding:const EdgeInsets.symmetric(horizontal:12,vertical:6),onPressed:busy||!canChooseProvider?null:()=>chooseProvider(context),child:Row(mainAxisSize:MainAxisSize.min,children:[ProviderIcon(provider:provider,size:17),const SizedBox(width:7),Text(names[provider]??'Chọn AI',style:TextStyle(fontSize:13,color:color.onSurfaceVariant)),const SizedBox(width:4),Icon(CupertinoIcons.chevron_down,size:12,color:color.onSurfaceVariant)])))),
     IconButton(tooltip:'Tạo ảnh/video',onPressed:onMedia,icon:Icon(CupertinoIcons.wand_stars,size:21,color:color.primary)),
    ]),
    if(attachmentChips.isNotEmpty)SingleChildScrollView(scrollDirection:Axis.horizontal,child:Row(children:attachmentChips)),
    Row(crossAxisAlignment:CrossAxisAlignment.end,children:[
     IconButton(tooltip:'Đính kèm file',onPressed:onAttach,icon:const Icon(CupertinoIcons.add,size:25)),
     Expanded(child:TextField(controller:controller,onChanged:(_)=>onChanged(),minLines:1,maxLines:4,maxLength:12000,
      style:const TextStyle(fontSize:16),decoration:const InputDecoration(filled:false,hintText:'Hỏi Chat AI…',counterText:'',contentPadding:EdgeInsets.symmetric(vertical:12,horizontal:2),border:InputBorder.none,enabledBorder:InputBorder.none,focusedBorder:InputBorder.none))),
     IconButton(tooltip:listening?'Dừng nghe':'Nhập bằng giọng nói',onPressed:onMicrophone,icon:Icon(listening?CupertinoIcons.mic_slash:CupertinoIcons.mic,size:23),color:listening?Colors.redAccent:null),
     IconButton.filled(tooltip:busy?'Dừng chờ':empty?'Trò chuyện giọng nói':'Gửi tin nhắn',onPressed:onAction,
      style:IconButton.styleFrom(backgroundColor:color.primary,foregroundColor:Colors.white,shape:const CircleBorder()),icon:Icon(busy?CupertinoIcons.stop_fill:empty?CupertinoIcons.waveform:CupertinoIcons.arrow_up,size:21)),
    ]),
   ]))));
 }
}
