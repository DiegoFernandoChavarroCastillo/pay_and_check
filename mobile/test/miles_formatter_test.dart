import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pay_and_check/core/format.dart';
import 'package:pay_and_check/core/widgets.dart';

void main() {
  test('agrupa miles y conserva decimales', () {
    expect(MilesFormatter.agrupar('1200000'), '1.200.000');
    expect(MilesFormatter.agrupar('18.500'), '18.500');
    expect(MilesFormatter.agrupar('999'), '999');
    expect(MilesFormatter.agrupar('1234,5'), '1.234,5');
    expect(MilesFormatter.agrupar(''), '');
    expect(parseMoney(MilesFormatter.agrupar('1200000')), 1200000);
  });

  test('el cursor queda después del dígito escrito', () {
    const f = MilesFormatter();
    final r = f.formatEditUpdate(
      const TextEditingValue(text: '120.000'),
      const TextEditingValue(text: '1200000', selection: TextSelection.collapsed(offset: 7)),
    );
    expect(r.text, '1.200.000');
    expect(r.selection.end, 9);
  });
}
