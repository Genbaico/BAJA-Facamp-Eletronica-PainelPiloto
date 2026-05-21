/*
 * RECEPTOR - SIM808 + Arduino Mega
 * Recebe SMS com coordenadas GPS do transmissor e exibe no Serial Monitor
 *
 * Conexões:
 *   SIM808 TXD -> Arduino pino 10
 *   SIM808 RXD -> Arduino pino 11
 *   GND comum entre Arduino e SIM808
 *   Alimentação externa recomendada para o SIM808 (4V, mín. 2A)
 */

#include <SoftwareSerial.h>

SoftwareSerial sim808(10, 11); // RX, TX

String bufferSerial = "";

void setup() {
  Serial.begin(9600);
  sim808.begin(9600);

  Serial.println(F("=== RECEPTOR SIM808 ==="));
  delay(3000);

  // Testa comunicação
  enviarComando("AT", 1000);

  // Configura SMS em modo texto
  enviarComando("AT+CMGF=1", 1000);

  // Define charset
  enviarComando("AT+CSCS=\"GSM\"", 1000);

  // Configura notificação automática quando chegar SMS
  // +CMTI: "SM",<index>
  enviarComando("AT+CNMI=2,1,0,0,0", 1000);

  // Apaga SMS antigos para evitar confusão
  enviarComando("AT+CMGDA=\"DEL ALL\"", 2000);

  Serial.println(F("Receptor pronto. Aguardando mensagens..."));
}

void loop() {
  // Lê continuamente da serial do SIM808
  while (sim808.available()) {
    char c = sim808.read();
    bufferSerial += c;

    // Quando recebe quebra de linha, processa o conteúdo
    if (c == '\n') {
      processarLinha(bufferSerial);
      bufferSerial = "";
    }
  }
}

// Verifica se chegou uma notificação de SMS
void processarLinha(String linha) {
  linha.trim();
  if (linha.length() == 0) return;

  // Quando chega SMS aparece: +CMTI: "SM",N
  if (linha.startsWith("+CMTI:")) {
    int virgula = linha.indexOf(',');
    int indice = linha.substring(virgula + 1).toInt();

    Serial.print(F("Novo SMS no indice: "));
    Serial.println(indice);

    lerSMS(indice);
  }
}

// Lê o SMS no índice informado
void lerSMS(int indice) {
  sim808.print("AT+CMGR=");
  sim808.println(indice);

  delay(2000);

  String resposta = "";
  while (sim808.available()) {
    resposta += (char)sim808.read();
  }

  Serial.println(F("---- SMS RECEBIDO ----"));
  Serial.println(resposta);
  Serial.println(F("----------------------"));

  // Extrai os dados de latitude/longitude
  int latIdx = resposta.indexOf("LAT:");
  int lonIdx = resposta.indexOf("LON:");

  if (latIdx != -1 && lonIdx != -1) {
    String lat = resposta.substring(latIdx + 4, resposta.indexOf(',', latIdx));
    String lon = resposta.substring(lonIdx + 4);
    lon.trim();

    // Remove caracteres extras do final
    int corte = lon.indexOf('\r');
    if (corte != -1) lon = lon.substring(0, corte);

    Serial.println(F(">>> COORDENADAS RECEBIDAS <<<"));
    Serial.println("Latitude:  " + lat);
    Serial.println("Longitude: " + lon);
    Serial.println("Link Maps: https://maps.google.com/?q=" + lat + "," + lon);
  }

  // Apaga o SMS depois de ler para liberar espaço
  sim808.print("AT+CMGD=");
  sim808.println(indice);
  delay(1000);
}

// Função auxiliar para comandos AT
void enviarComando(String cmd, int espera) {
  sim808.println(cmd);
  delay(espera);
  while (sim808.available()) {
    Serial.write(sim808.read());
  }
}
