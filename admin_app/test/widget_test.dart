import 'package:flutter_test/flutter_test.dart';
import 'package:matar_admin/main.dart';

void main() {
  test('Matar admin app points to the current HTTPS service', () {
    expect(apiBase, startsWith('https://'));
    expect(apiBase, contains('matar-bot.onrender.com'));
  });
}
