# google_mlkit_text_recognition referencia los reconocedores de chino,
# devanagari, japonés y coreano, que son dependencias opcionales. La app solo
# usa el de escritura latina, así que esas clases no están y R8 debe ignorarlas
# en vez de abortar el build de release.
-dontwarn com.google.mlkit.vision.text.chinese.**
-dontwarn com.google.mlkit.vision.text.devanagari.**
-dontwarn com.google.mlkit.vision.text.japanese.**
-dontwarn com.google.mlkit.vision.text.korean.**
