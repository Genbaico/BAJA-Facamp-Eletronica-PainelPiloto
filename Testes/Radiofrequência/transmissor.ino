/*
 * TRANSMISSOR - SIM808 + Arduino Mega
 * Envia coordenadas GPS via SMS para o receptor
 * 
 * Conexões:
 *   SIM808 TXD -> Arduino pino 10
 *   SIM808 RXD -> Arduino pino 11
 *   GND comum entre Arduino e SIM808
 *   Alimentação externa recomendada para o SIM808 (4V, mín. 2A)
 */

#include <SoftwareSerial.h>

// Pinos de comunicação com o SIM808
SoftwareSerial sim808(10, 11); // RX, TX no Arduino (cruzado com o SIM808)

// >>> COLOQUE AQUI O NÚMERO DO CHIP DO RECEPTOR <<<
const String NUMERO_RECEPTOR = "+5519999999999"; // formato internacional

// Intervalo entre envios (em milissegundos)
const unsigned long INTERVALO_ENVIO = 60000; // 1 minuto

unsigned long ultimoEnvio = 0;

// Variáveis para armazenar dados do GPS
String latitude  = "";
String longitude = "";
bool gpsValido   = false;

void setup() {
  Serial.begin(9600);
  sim808.begin(9600);

  Serial.println(F("=== TRANSMISSOR SIM808 ==="));
  delay(3000);

  // Testa comunicação básica
  enviarComando("AT", 1000);

  // Configura SMS em modo texto
  enviarComando("AT+CMGF=1", 1000);

  // Define conjunto de caracteres
  enviarComando("AT+CSCS=\"GSM\"", 1000);

  // Liga o GPS
  Serial.println(F("Ligando GPS..."));
  enviarComando("AT+CGNSPWR=1", 1000);
  delay(2000);

  // Define sequência NMEA
  enviarComando("AT+CGNSSEQ=\"RMC\"", 1000);

  Serial.println(F("Aguardando sinal GPS (pode levar alguns minutos)..."));
  delay(5000);
}

void loop() {
  // Lê a posição GPS continuamente
  lerGPS();

  // Envia SMS no intervalo definido
  if (millis() - ultimoEnvio >= INTERVALO_ENVIO) {
    if (gpsValido) {
      String mensagem = "LAT:" + latitude + ",LON:" + longitude;
      Serial.println("Enviando: " + mensagem);
      enviarSMS(NUMERO_RECEPTOR, mensagem);
    } else {
      Serial.println(F("GPS ainda sem fixo. Tentando novamente..."));
    }
    ultimoEnvio = millis();
  }

  delay(2000);
}

// Envia comando AT e mostra a resposta no monitor serial
void enviarComando(String cmd, int espera) {
  sim808.println(cmd);
  delay(espera);
  while (sim808.available()) {
    Serial.write(sim808.read());
  }
}

// Lê informações do GPS (AT+CGNSINF)
void lerGPS() {
  sim808.println("AT+CGNSINF");
  delay(1000);

  String resposta = "";
  while (sim808.available()) {
    resposta += (char)sim808.read();
  }

  // Resposta exemplo:
  // +CGNSINF: 1,1,20240101120000.000,-22.7332,-47.1543,580.0,...
  int idx = resposta.indexOf("+CGNSINF:");
  if (idx == -1) {
    gpsValido = false;
    return;
  }

  // Pula até o segundo campo (fix status)
  int p1 = resposta.indexOf(',', idx);
  int p2 = resposta.indexOf(',', p1 + 1);
  String fix = resposta.substring(p1 + 1, p2);

  if (fix != "1") {
    gpsValido = false;
    return;
  }

  // Pula data/hora
  int p3 = resposta.indexOf(',', p2 + 1);
  // Latitude
  int p4 = resposta.indexOf(',', p3 + 1);
  latitude = resposta.substring(p3 + 1, p4);
  // Longitude
  int p5 = resposta.indexOf(',', p4 + 1);
  longitude = resposta.substring(p4 + 1, p5);

  if (latitude.length() > 0 && longitude.length() > 0) {
    gpsValido = true;
    Serial.println("GPS OK -> Lat: " + latitude + " | Lon: " + longitude);
  } else {
    gpsValido = false;
  }
}

// Envia um SMS para o número informado
void enviarSMS(String numero, String texto) {
  sim808.print("AT+CMGS=\"");
  sim808.print(numero);
  sim808.println("\"");
  delay(1000);

  sim808.print(texto);
  delay(500);

  sim808.write(26); // CTRL+Z para enviar
  delay(5000);

  Serial.println(F("SMS enviado!"));
  while (sim808.available()) {
    Serial.write(sim808.read());
  }
}
