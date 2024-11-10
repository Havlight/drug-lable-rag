import 'package:flutter/material.dart';

class DataProvider extends ChangeNotifier {
  List<Map<String, String>> data = [];

  void addNewData(String title, String note) {
    data.add({
      "date": DateTime.now().toString(),
      "title": title,
      "note": note
    });
    notifyListeners();
  }

  void editData(int index, String title, String note) {
    data[index]["title"] = title;
    data[index]["note"] = note;
    notifyListeners();
  }

  void removeData(int index) {
    data.removeAt(index);
    notifyListeners();
  }
}
