import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:async';

Future<Uint8List?> pickImageFromGallery() async {
  html.FileUploadInputElement uploadInput = html.FileUploadInputElement()..accept = 'image/*';
  uploadInput.click();

  final Completer<Uint8List?> completer = Completer();
  uploadInput.onChange.listen((event) async {
    final reader = html.FileReader();
    reader.readAsArrayBuffer(uploadInput.files!.first);
    reader.onLoadEnd.listen((event) {
      completer.complete(reader.result as Uint8List?);
    });
  });

  return completer.future;
}

Future<Uint8List?> pickImageFromCamera() async {
  return pickImageFromGallery(); // Web 端沒有相機 API，使用相簿選取代替
}
