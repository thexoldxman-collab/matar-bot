import 'package:flutter_test/flutter_test.dart';
import 'package:matar_admin/main.dart';

void main() {
  test('admin app uses the existing HTTPS Render service', () {
    expect(apiBase, startsWith('https://'));
    expect(apiBase, contains('matar-bot.onrender.com'));
  });
}
