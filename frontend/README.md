![image](https://github.com/user-attachments/assets/16240b3b-92bd-4df4-8c55-d86da9eced42)
如果要用web要先在設定開啟Google WEB Driver
在環境用好後要檢查  
1.flutter devices，確認 Web 支援是否啟用  
2.flutter upgrade， 確保是最新的 Flutter  
3.flutter pub upgrade，更新套件  
這三個沒問題基本上不會有啥事
然後web要用指令開 : flutter run -d chrome

AndroidManifest.xml的路徑 : "資料夾名稱\android\app\src\main\AndroidManifest.xml"  
pubspec.yaml : 就在資料夾下
