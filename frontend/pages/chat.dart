import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '/global.dart' as globals;
import 'Login_page.dart';
import 'web_image_picker.dart' if (dart.library.io) 'mobile_image_picker.dart';

class ChatScreen extends StatefulWidget {
  @override
  _ChatScreenState createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _messageController = TextEditingController();
  List<Map<String, dynamic>> _messages = [];

  @override
  void initState() {
    super.initState();
    _loadChatHistory();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('藥師傅方便問'),
        actions: [
          IconButton(
            icon: Icon(Icons.logout),
            onPressed: _logout,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[index];
                return _buildMessageBubble(message);
              },
            ),
          ),
          _buildMessageInputArea(),
        ],
      ),
    );
  }

  Widget _buildMessageInputArea() {
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Row(
        children: [
          IconButton(
            icon: Icon(Icons.camera_alt),
            onPressed: _pickImageFromCamera,
          ),
          IconButton(
            icon: Icon(Icons.image),
            onPressed: _pickImageFromGallery,
          ),
          Expanded(
            child: TextField(
              controller: _messageController,
              decoration: InputDecoration(
                hintText: 'Enter a message',
              ),
            ),
          ),
          IconButton(
            icon: Icon(Icons.send),
            onPressed: _sendMessage,
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> message) {
    bool isUserMessage = message['isUser'] ?? false;
    bool isLoading = message['isLoading'] ?? false;//如果為空初始化為false

    return Align(
      alignment: isUserMessage ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: EdgeInsets.symmetric(vertical: 5, horizontal: 10),
        padding: EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: isUserMessage ? Colors.green : Colors.blue,
          borderRadius: BorderRadius.circular(15),
        ),
        child: isLoading
            ? Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(width: 10),
            Text('Sending...'),
          ],
        )
            : Column(
          crossAxisAlignment: isUserMessage
              ? CrossAxisAlignment.end
              : CrossAxisAlignment.start,
          children: [
            if (message.containsKey('widget')) // URL
              message['widget'] as Widget
            else
              MarkdownBody(
                data: message['text'] ?? '',
                selectable: true,
                styleSheet: MarkdownStyleSheet(
                  a: TextStyle(color: Colors.red), // 超連結設定
                ),
                onTapLink: (text, url, title) async {
                  if (url != null) {
                    final Uri uri = Uri.parse(url);
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri);
                    } else {
                      print("無法啟動 $url");
                    }
                  }
                },
              ),
            if (message['image'] != null)
              kIsWeb
                  ? Image.memory(message['image'])
                  : Image.file(message['image'], width: 100, height: 100),
          ],
        ),
      ),
    );
  }

  Future<void> _sendMessage() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();//讀取和寫入本地儲存中的數據
    String? token = prefs.getString('access_token');
    String historyKey = 'chat_history_$token';//區分不同使用者的聊天記錄或歷史紀錄

    if (_messageController.text.isNotEmpty) {
      String textToSend = _messageController.text;

      List<String> historyList = [];//存歷史記錄的list

      setState(() {
        _messages.add({'text': textToSend, 'isUser': true});
        _messageController.clear();
        _messages.add({'text': '...', 'isLoading': true, 'isUser': false});
      });

      final url = Uri.parse('http://${globals.localhost}/chat');
      final response = await http.post(
        url,
        headers: <String, String>{
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json; charset=UTF-8',
        },
        body: jsonEncode(<String, dynamic>{
          'prompt': textToSend,
          'history': historyList,
          'docs': [],
        }),
      );//回傳後端

      setState(() {
        _messages.removeWhere((msg) => msg['isLoading'] == true);
      });

      if (response.statusCode == 200) {
        final responseData = jsonDecode(utf8.decode(response.bodyBytes));
        String reply = responseData['reply'] ?? '沒有回應';

        String updatedReply = reply;

        if (responseData.containsKey('documents')) {
          var documents = responseData['documents'];
          if (documents is List) {
            for (var doc in documents) {
              if (doc.containsKey('s')) {
                String documentS = doc['s'];
                final matches = RegExp(r'第(\d{6})號-(.+?)-').allMatches(documentS);

                for (final match in matches) {
                  final code = match.group(1); // 藥品號
                  final drugName = match.group(2); // 藥品名稱

                  if (code != null && drugName != null) {
                    String link;

                    if (documentS.contains('一般仿單')) {
                      link = 'https://mcp.fda.gov.tw/im_detail_pdf/衛署藥製字第$code號/';
                    } else if (documentS.contains('電子仿單')) {
                      link = 'https://mcp.fda.gov.tw/im_detail_1/衛署藥輸字第$code號/';
                    } else {
                      link = 'https://mcp.fda.gov.tw/im_detail_pdf/衛署藥製字第$code號/';
                    }

                    // 區隔藥名跟號碼
                    updatedReply += '\n[$drugName (第$code號)]($link)\n\n';
                    historyList.add(link);
                  }
                }
              }
            }
          }
        }


        _simulateMessageReceived(updatedReply);
        _saveChatHistory(historyKey);
      } else {
        _simulateMessageReceived('發生錯誤: ${response.reasonPhrase}');
      }
    }
  }

  void _simulateMessageReceived(String reply) {
    setState(() {
      _messages.add({
        'text': reply,
        'isUser': false,
      });
    });
  }

  Future<void> _saveChatHistory(String historyKey) async {
    SharedPreferences prefs = await SharedPreferences.getInstance();

    if (_messages.length > 10) {
      _messages = _messages.sublist(_messages.length - 10);
    }//只保留10筆

    List<String> history = _messages
        .where((msg) => msg.containsKey('text'))
        .map((msg) => jsonEncode({'text': msg['text'], 'isUser': msg['isUser']}))
        .toList();

    await prefs.setStringList(historyKey, history);
  }

  Future<void> _loadChatHistory() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    String? token = prefs.getString('access_token');
    String historyKey = 'chat_history_$token';

    List<String>? history = prefs.getStringList(historyKey);
    if (history != null) {
      setState(() {
        _messages = history.map((msg) => jsonDecode(msg) as Map<String, dynamic>).toList();
      });
    }
  }

  void _pickImageFromCamera() async {
    final pickedFile = await pickImageFromCamera();
    if (pickedFile != null) {
      setState(() {
        _messages.add({'image': pickedFile, 'isUser': true});
      });
      _saveChatHistory('chat_history_${await _getToken()}');
    }
  }

  void _pickImageFromGallery() async {
    final pickedFile = await pickImageFromGallery();
    if (pickedFile != null) {
      setState(() {
        _messages.add({'image': pickedFile, 'isUser': true});
      });
      _saveChatHistory('chat_history_${await _getToken()}');
    }
  }

  Future<void> _logout() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => LoginPage()),
    );
  }

  Future<String?> _getToken() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString('access_token');
  }
}
