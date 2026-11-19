package co.medtender.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class MedtenderApplication {

    public static void main(String[] args) {
        SpringApplication.run(MedtenderApplication.class, args);
    }
}
