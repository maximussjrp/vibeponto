# VibePonto Mobile

Aplicativo móvel do VibePonto - Sistema de Controle de Ponto desenvolvido em Flutter.

## 📱 Funcionalidades

### Autenticação
- ✅ Login com email e senha
- ✅ Autenticação em dois fatores (MFA)
- ✅ Login biométrico (impressão digital/Face ID)
- ✅ Persistência de sessão segura

### Registro de Ponto
- ✅ Bater ponto com localização GPS
- ✅ Captura de foto (opcional)
- ✅ Tipos de registro: Entrada, Saída Almoço, Retorno Almoço, Saída
- ✅ Validação de geofencing em tempo real

### Histórico
- ✅ Visualização por mês
- ✅ Detalhes de cada registro
- ✅ Status de aprovação

### Espelho de Ponto
- ✅ Visualização mensal completa
- ✅ Cálculo de horas trabalhadas
- ✅ Saldo de horas
- ✅ Exportação em PDF

### Perfil
- ✅ Informações pessoais
- ✅ Dados profissionais
- ✅ Configurações de segurança

## 🚀 Tecnologias

- **Flutter** 3.16+ - Framework de desenvolvimento
- **Dart** 3.2+ - Linguagem de programação
- **flutter_bloc** - Gerenciamento de estado
- **go_router** - Navegação
- **dio** - Cliente HTTP
- **geolocator** - Localização GPS
- **image_picker** - Captura de fotos
- **flutter_secure_storage** - Armazenamento seguro
- **local_auth** - Biometria
- **hive** - Cache local

## 📋 Pré-requisitos

- Flutter SDK 3.16 ou superior
- Dart SDK 3.2 ou superior
- Android Studio / Xcode
- Dispositivo físico ou emulador

## 🔧 Instalação

1. Clone o repositório:
```bash
cd mobile
```

2. Instale as dependências:
```bash
flutter pub get
```

3. Gere os arquivos de código:
```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

4. Execute o aplicativo:
```bash
flutter run
```

## 📁 Estrutura do Projeto

```
lib/
├── core/
│   ├── di/           # Injeção de dependências
│   ├── network/      # Cliente HTTP e interceptors
│   ├── router/       # Configuração de rotas
│   ├── storage/      # Armazenamento seguro
│   └── theme/        # Tema da aplicação
├── features/
│   ├── auth/         # Autenticação
│   │   ├── data/
│   │   ├── domain/
│   │   └── presentation/
│   ├── home/         # Tela principal
│   ├── ponto/        # Registro de ponto
│   ├── perfil/       # Perfil do usuário
│   └── espelho/      # Espelho de ponto
└── main.dart
```

## 🔒 Permissões Necessárias

### Android (AndroidManifest.xml)
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.USE_BIOMETRIC"/>
```

### iOS (Info.plist)
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Precisamos da localização para registrar seu ponto.</string>
<key>NSCameraUsageDescription</key>
<string>Precisamos da câmera para capturar foto ao bater ponto.</string>
<key>NSFaceIDUsageDescription</key>
<string>Use Face ID para fazer login rapidamente.</string>
```

## 🧪 Testes

```bash
# Executar todos os testes
flutter test

# Executar com cobertura
flutter test --coverage
```

## 📦 Build

### Android
```bash
flutter build apk --release
# ou para App Bundle
flutter build appbundle --release
```

### iOS
```bash
flutter build ios --release
```

## 🔐 Configuração de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
API_BASE_URL=http://localhost:8000/api/v1
```

## 📱 Screenshots

[Adicionar screenshots aqui]

## 🤝 Contribuição

1. Fork o projeto
2. Crie sua branch de feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob licença privada - VibePonto © 2024
